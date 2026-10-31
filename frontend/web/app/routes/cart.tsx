import { ImageOff, ShoppingCart, Trash2 } from "lucide-react";
import { data, useFetcher } from "react-router";

import { ButtonLink, Card, EmptyState, PageTitle } from "~/components/ui";
import { langFromRequest, makeT } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { cartLines, cartTotal, getCart, saveCart } from "~/lib/cart.server";
import { apiContext } from "~/lib/context.server";
import { formatPrice, formatQty } from "~/lib/format";
import { sessionContext } from "~/lib/session.server";
import type { CartItem } from "~/lib/types";
import { thumb } from "~/lib/thumb";

import type { Route } from "./+types/cart";

export const meta: Route.MetaFunction = ({ matches }) => {
  const lang = (matches[0]?.loaderData as { lang?: "uk" | "ru" } | undefined)?.lang ?? "uk";
  return [{ title: makeT(lang)("cart.title") }];
};

export async function loader({ context }: Route.LoaderArgs) {
  const cart = await getCart(context.get(apiContext), context.get(sessionContext));
  return { items: cart?.cart_items ?? [], total: cartTotal(cart) };
}

/** intent: add (product, variant, quantity) · set (variant, quantity) · remove (variant) · clear */
export async function action({ request, context }: Route.ActionArgs) {
  const api = context.get(apiContext);
  const session = context.get(sessionContext);
  const form = await request.formData();
  const intent = String(form.get("intent"));
  const variant = Number(form.get("variant")) || null;
  const quantity = Math.max(0, Math.floor(Number(form.get("quantity")) || 0));
  const t = makeT(langFromRequest(request));

  try {
    let lines = cartLines(await getCart(api, session));
    if (intent === "add") {
      const product = Number(form.get("product"));
      const existing = lines.find((l) => l.variant === variant);
      if (existing) existing.quantity += Math.max(1, quantity);
      else lines.push({ product, variant, quantity: Math.max(1, quantity) });
    } else if (intent === "set") {
      lines = lines.map((l) => (l.variant === variant ? { ...l, quantity: Math.max(1, quantity) } : l));
    } else if (intent === "remove") {
      lines = lines.filter((l) => l.variant !== variant);
    } else if (intent === "clear") {
      lines = [];
    } else {
      return data({ ok: false, error: t("cart.unknownAction") }, { status: 400 });
    }
    await saveCart(api, session, lines);
    return { ok: true };
  } catch (e) {
    const message = e instanceof ApiError ? Object.values(e.fieldErrors)[0] : t("cart.error");
    return data({ ok: false, error: message }, { status: 400 });
  }
}

export default function CartPage({ loaderData }: Route.ComponentProps) {
  const { items, total } = loaderData;
  const t = useT();
  if (!items.length) {
    return (
      <EmptyState icon={ShoppingCart} title={t("cart.empty.title")}>
        <p className="mb-4">{t("cart.empty.text")}</p>
        <ButtonLink to="/catalog">{t("common.toCatalog")}</ButtonLink>
      </EmptyState>
    );
  }
  const overLimit = items.some((i) => i.available !== null && i.quantity > Number(i.available));
  return (
    <div>
      <PageTitle>{t("cart.title")}</PageTitle>
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <ul className="space-y-3">
          {items.map((item) => (
            <CartRow key={item.id} item={item} />
          ))}
        </ul>
        <Card className="space-y-4 self-start p-5 lg:sticky lg:top-24">
          <div className="flex items-baseline justify-between">
            <span className="text-muted">{t("cart.total")}</span>
            <span className="text-2xl font-bold">{formatPrice(total)}</span>
          </div>
          {overLimit && (
            <p className="text-sm text-danger">{t("cart.overLimit")}</p>
          )}
          <ButtonLink to="/checkout" size="lg" className={`w-full ${overLimit ? "pointer-events-none opacity-60" : ""}`} aria-disabled={overLimit}>
            {t("cart.checkout")}
          </ButtonLink>
          <Link to="/catalog" className="block text-center text-sm text-brand-600 hover:underline">
            {t("cart.continue")}
          </Link>
        </Card>
      </div>
    </div>
  );
}

function CartRow({ item }: { item: CartItem }) {
  const fetcher = useFetcher<{ ok: boolean; error?: string }>();
  const t = useT();
  const pending = fetcher.formData;
  // оптимистичное обновление: показываем новое количество сразу
  const quantity = pending?.get("intent") === "set" ? Number(pending.get("quantity")) : item.quantity;
  const removing = pending?.get("intent") === "remove";
  const available = item.available === null ? null : Number(item.available);
  if (removing) return null;
  return (
    <li className="flex gap-4 rounded-2xl border border-line bg-white p-4">
      <div className="grid size-20 shrink-0 place-items-center overflow-hidden rounded-xl bg-surface sm:size-24">
        {item.photo ? <img src={thumb(item.photo, 160)} alt="" className="size-full object-contain p-1" /> : <ImageOff className="size-6 text-muted" />}
      </div>
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex justify-between gap-3">
          <p className="font-medium">{item.product_name}</p>
          <fetcher.Form method="post">
            <input type="hidden" name="intent" value="remove" />
            <input type="hidden" name="variant" value={item.variant ?? ""} />
            <button type="submit" className="text-muted hover:text-danger" aria-label={t("cart.remove")}>
              <Trash2 className="size-5" />
            </button>
          </fetcher.Form>
        </div>
        <p className="text-sm text-muted">{t("cart.perUnit", { price: formatPrice(item.price) })}</p>
        <div className="mt-auto flex flex-wrap items-center justify-between gap-3">
          <fetcher.Form method="post" className="flex items-center gap-2">
            <input type="hidden" name="intent" value="set" />
            <input type="hidden" name="variant" value={item.variant ?? ""} />
            {[-1, 1].map((delta) => (
              <button
                key={delta}
                type="submit"
                name="quantity"
                value={quantity + delta}
                disabled={quantity + delta < 1 || (delta > 0 && available !== null && quantity >= available)}
                className="grid size-9 place-items-center rounded-lg border border-line text-lg disabled:opacity-40"
                aria-label={delta > 0 ? t("common.increase") : t("common.decrease")}
                style={{ order: delta < 0 ? 0 : 2 }}
              >
                {delta > 0 ? "+" : "−"}
              </button>
            ))}
            <span className="order-1 w-8 text-center font-medium" aria-live="polite">{quantity}</span>
          </fetcher.Form>
          <span className="font-semibold">{formatPrice(Number(item.price ?? 0) * quantity)}</span>
        </div>
        {available !== null && quantity > available && (
          <p className="text-sm text-danger">{t("cart.onlyLeft", { qty: formatQty(available) })}</p>
        )}
        {item.on_order && item.on_order_days ? (
          <p className="text-sm text-brand-700">{t("cart.onOrder", { days: item.on_order_days })}</p>
        ) : null}
        {fetcher.data?.error && <p className="text-sm text-danger">{fetcher.data.error}</p>}
      </div>
    </li>
  );
}
