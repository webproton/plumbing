import { Heart, Trash2 } from "lucide-react";
import { data, useFetcher } from "react-router";

import { AddToCartButton } from "~/components/AddToCartButton";
import { Price } from "~/components/Price";
import { ButtonLink, EmptyState, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { Link, useLocalPath, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { requireUser } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import type { WishlistItem } from "~/lib/types";

import type { Route } from "./+types/wishlist";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("wishlist.title") },
  { name: "robots", content: "noindex" },
];

export async function loader({ request, context }: Route.LoaderArgs) {
  requireUser(request, context);
  return { items: await context.get(apiContext).get<WishlistItem[]>("/wishlist/") };
}

export async function action({ request, context }: Route.ActionArgs) {
  requireUser(request, context);
  const form = await request.formData();
  const api = context.get(apiContext);
  try {
    if (form.get("intent") === "remove") await api.delete(`/wishlist/${Number(form.get("id"))}/`);
    else await api.post("/wishlist/", { product_variant_id: Number(form.get("variant")) });
    return { ok: true };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ ok: false }, { status: 400 });
  }
}

export default function Wishlist({ loaderData }: Route.ComponentProps) {
  const t = useT();
  if (!loaderData.items.length) {
    return (
      <EmptyState icon={Heart} title={t("wishlist.empty.title")}>
        <p className="mb-4">{t("wishlist.empty.text")}</p>
        <ButtonLink to="/catalog">{t("common.toCatalog")}</ButtonLink>
      </EmptyState>
    );
  }
  return (
    <div>
      <PageTitle>{t("wishlist.title")}</PageTitle>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loaderData.items.map((item) => (
          <WishlistCard key={item.id} item={item} />
        ))}
      </ul>
    </div>
  );
}

function WishlistCard({ item }: { item: WishlistItem }) {
  const fetcher = useFetcher();
  const t = useT();
  const local = useLocalPath();
  const v = item.product_variant;
  if (fetcher.formData) return null; // оптимистично убираем карточку
  return (
    <li className="flex gap-4 rounded-2xl border border-line bg-white p-4">
      {v.photo && <img src={v.photo} alt="" className="size-20 rounded-xl bg-surface object-contain" />}
      <div className="flex flex-1 flex-col gap-2">
        <Link to={`/product/${item.productSlug}?v=${v.id}`} className="font-medium hover:text-brand-600">
          {v.product_name}
        </Link>
        <Price value={v.price} original={v.original_price} />
        <div className="mt-auto flex gap-2">
          <AddToCartButton
            productId={v.product.id}
            variantId={v.id}
            disabled={!v.in_stock}
            size="sm"
            className="flex-1"
            track={{ id: v.id, name: v.product_name ?? v.product.name ?? "", price: Number(v.price ?? 0) }}
          />
          <fetcher.Form method="post" action={local("/wishlist")}>
            <input type="hidden" name="intent" value="remove" />
            <input type="hidden" name="id" value={item.id} />
            <button type="submit" className="grid size-9 place-items-center rounded-xl border border-line text-muted hover:text-danger" aria-label={t("wishlist.remove")}>
              <Trash2 className="size-4" />
            </button>
          </fetcher.Form>
        </div>
      </div>
    </li>
  );
}
