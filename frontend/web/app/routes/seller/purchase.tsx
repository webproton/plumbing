import {
  Check,
  ClipboardList,
  Copy,
  History,
  Minus,
  Plus,
  Printer,
  Search,
  ShoppingCart,
  Trash2,
  Truck,
} from "lucide-react";
import { useState } from "react";
import { data, Form, useNavigation } from "react-router";

import { Alert, Button, ButtonLink, EmptyState, PageTitle, SuggestionNote } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { formatPrice, formatQty } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";

import type { Route } from "./+types/purchase";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("pur.nav") }];

interface Choice {
  variant: number | null;
  item: number | null;
  name: string;
  supplier: number | null;
  supplier_name: string;
  price: string | null;
  date?: string;
}
interface Line {
  id: number;
  text: string;
  quantity: string;
  unit: string;
  auto: boolean;
  choice: Choice | null;
  supplier_name: string;
  price: string | null;
}
interface PurchaseList {
  id: number;
  lines: Line[];
}
interface Offer {
  supplier: number | null;
  supplier_name: string;
  price: string | null;
  kind: "feed" | "invoice" | "manual";
  date: string | null;
  available: boolean | null;
  best: boolean;
}
interface Options {
  suggestion: string | null;
  last_time: Choice | null;
  products: { variant: number; name: string; sku: string; stock: string; offers: Offer[] }[];
  items: {
    item: number;
    name: string;
    sku: string;
    supplier_name: string;
    price: string | null;
    raw_price: string | null;
    currency: string;
    available: boolean | null;
  }[];
}
interface OrderGroup {
  key: string;
  supplier: string;
  phone: string;
  total: string;
  message: string;
  lines: {
    id: number;
    text: string;
    name: string;
    sku: string;
    quantity: string;
    unit: string;
    price: string | null;
    total: string | null;
  }[];
}

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const url = new URL(request.url);
  const lineId = Number(url.searchParams.get("line")) || null;
  const view = url.searchParams.get("view") === "order" ? "order" : "list";
  const [list, options, order] = await Promise.all([
    api.get<PurchaseList>("/warehouse/purchase/"),
    lineId
      ? api.get<Options>(`/warehouse/purchase/lines/${lineId}/options/`).catch(() => null)
      : Promise.resolve(null),
    view === "order"
      ? api.get<{ groups: OrderGroup[] }>("/warehouse/purchase/assemble/")
      : Promise.resolve(null),
  ]);
  return { list, options, lineId, view, order };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const intent = String(form.get("intent"));
  const line = Number(form.get("line"));
  try {
    if (intent === "add") {
      const texts = String(form.get("texts") ?? "")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      if (!texts.length) return data({ ok: false as const, message: t("pur.emptyLine") }, { status: 400 });
      const r = await api.post<{ created: number[] }>("/warehouse/purchase/lines/", { texts });
      return { ok: true as const, message: t("pur.added", { n: r.created.length }) };
    }
    if (intent === "qty") {
      await api.patch(`/warehouse/purchase/lines/${line}/`, { quantity: String(form.get("quantity")) });
      return { ok: true as const, message: "" };
    }
    if (intent === "choose") {
      const item = Number(form.get("item")) || null;
      await api.patch(
        `/warehouse/purchase/lines/${line}/`,
        item
          ? { item }
          : {
              variant: Number(form.get("variant")),
              supplier: Number(form.get("supplier")) || null,
              supplier_name: String(form.get("supplier_name") ?? ""),
              price: form.get("price") || null,
            },
      );
      return { ok: true as const, message: t("pur.chosen"), close: true };
    }
    if (intent === "clear") {
      await api.patch(`/warehouse/purchase/lines/${line}/`, { clear: true });
      return { ok: true as const, message: "", close: true };
    }
    if (intent === "delete") {
      await api.delete(`/warehouse/purchase/lines/${line}/`);
      return { ok: true as const, message: t("pur.deleted") };
    }
    if (intent === "ordered") {
      await api.post("/warehouse/purchase/ordered/", {});
      return { ok: true as const, message: t("pur.orderedDone") };
    }
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, message: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
  return data({ ok: false as const, message: t("error.generic") }, { status: 400 });
}

const big = "text-base sm:text-lg";

function QtyStepper({ line }: { line: Line }) {
  const t = useT();
  const qty = Number(line.quantity);
  const step = (value: number) => (
    <Form method="post" className="contents">
      <input type="hidden" name="intent" value="qty" />
      <input type="hidden" name="line" value={line.id} />
      <input type="hidden" name="quantity" value={value} />
      <button
        type="submit"
        disabled={value <= 0}
        aria-label={value > qty ? t("pur.more") : t("pur.less")}
        className="border-line hover:bg-surface grid size-11 place-items-center rounded-full border bg-white disabled:opacity-40"
      >
        {value > qty ? <Plus className="size-5" aria-hidden /> : <Minus className="size-5" aria-hidden />}
      </button>
    </Form>
  );
  return (
    <div className="flex items-center gap-2">
      {step(qty - 1)}
      <span className={`${big} min-w-14 text-center font-semibold`}>
        {formatQty(line.quantity)}{" "}
        <span className="text-muted text-sm font-normal">{line.unit || t("pur.pcs")}</span>
      </span>
      {step(qty + 1)}
    </div>
  );
}

function LineCard({ line, open, options }: { line: Line; open: boolean; options: Options | null }) {
  const t = useT();
  return (
    <li className={`border-line rounded-2xl border bg-white p-4 ${open ? "ring-brand-100 ring-4" : ""}`}>
      <div className="flex flex-wrap items-center gap-3">
        <QtyStepper line={line} />
        <p className={`${big} min-w-0 flex-1 basis-48 font-semibold break-words`}>{line.text}</p>
        <Form method="post">
          <input type="hidden" name="intent" value="delete" />
          <input type="hidden" name="line" value={line.id} />
          <button
            type="submit"
            aria-label={t("pur.delete")}
            className="text-muted hover:text-danger grid size-11 place-items-center rounded-full"
          >
            <Trash2 className="size-5" aria-hidden />
          </button>
        </Form>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {line.choice ? (
          <p className="text-success flex min-w-0 flex-1 items-start gap-2 text-base">
            <Check className="mt-0.5 size-5 shrink-0" aria-hidden />
            <span className="text-ink">
              <b>{line.choice.name}</b>
              {line.supplier_name && <> · {line.supplier_name}</>}
              {line.price && <> · {formatPrice(line.price)}</>}
              {line.auto && <span className="text-muted block text-sm">{t("pur.autoHint")}</span>}
            </span>
          </p>
        ) : (
          <p className="text-muted flex-1 text-base">{t("pur.notChosen")}</p>
        )}
        <ButtonLink
          to={open ? "/seller/purchase" : `/seller/purchase?line=${line.id}`}
          preventScrollReset
          variant={line.choice ? "secondary" : "primary"}
          className="!px-5"
        >
          {open ? t("pur.close") : line.choice ? t("pur.change") : t("pur.pick")}
        </ButtonLink>
      </div>
      {open && options && <OptionsPanel line={line} options={options} />}
    </li>
  );
}

function ChooseButton({
  line,
  children,
  fields,
}: {
  line: Line;
  children: React.ReactNode;
  fields: Record<string, string | number | null>;
}) {
  const busy = useNavigation().state === "submitting";
  return (
    <Form method="post" preventScrollReset>
      <input type="hidden" name="intent" value="choose" />
      <input type="hidden" name="line" value={line.id} />
      {Object.entries(fields).map(([k, v]) => (
        <input key={k} type="hidden" name={k} value={v ?? ""} />
      ))}
      <button
        type="submit"
        disabled={busy}
        className="border-line hover:border-brand-500 hover:bg-brand-50 w-full rounded-xl border bg-white px-4 py-3 text-left text-base transition disabled:opacity-60"
      >
        {children}
      </button>
    </Form>
  );
}

function OptionsPanel({ line, options }: { line: Line; options: Options }) {
  const t = useT();
  const nothing = !options.last_time && !options.products.length && !options.items.length;
  return (
    <div className="mt-4 space-y-4 border-t border-dashed pt-4">
      {options.suggestion && <SuggestionNote query={line.text} suggestion={options.suggestion} />}
      {options.last_time && (
        <section className="space-y-2">
          <h3 className="flex items-center gap-2 font-semibold">
            <History className="text-brand-600 size-5" aria-hidden /> {t("pur.lastTime")}
          </h3>
          <ChooseButton
            line={line}
            fields={
              options.last_time.item
                ? { item: options.last_time.item }
                : {
                    variant: options.last_time.variant,
                    supplier: options.last_time.supplier,
                    supplier_name: options.last_time.supplier_name,
                    price: options.last_time.price,
                  }
            }
          >
            <b>{options.last_time.name}</b> · {options.last_time.supplier_name || t("pur.noSupplier")}
            {options.last_time.price && <> · {formatPrice(options.last_time.price)}</>}
          </ChooseButton>
        </section>
      )}
      {options.products.length > 0 && (
        <section className="space-y-3">
          <h3 className="flex items-center gap-2 font-semibold">
            <ShoppingCart className="text-brand-600 size-5" aria-hidden /> {t("pur.yourProducts")}
          </h3>
          {options.products.map((p) => (
            <div key={p.variant} className="bg-surface space-y-2 rounded-xl p-3">
              <p className="text-base">
                <b>{p.name}</b>
                <span className="text-muted text-sm">
                  {p.sku && ` · ${p.sku}`} · {t("pur.inStock", { n: formatQty(p.stock) })}
                </span>
              </p>
              {p.offers.length ? (
                p.offers.map((o) => (
                  <ChooseButton
                    key={`${o.kind}-${o.supplier ?? o.supplier_name}`}
                    line={line}
                    fields={{
                      variant: p.variant,
                      supplier: o.supplier,
                      supplier_name: o.supplier_name,
                      price: o.price,
                    }}
                  >
                    <span className="flex flex-wrap items-baseline justify-between gap-2">
                      <span>
                        <b>{o.supplier_name}</b>
                        <span className="text-muted text-sm">
                          {" "}
                          · {t(`pur.kind.${o.kind}`)}
                          {o.date && o.kind === "invoice"
                            ? ` ${new Date(o.date).toLocaleDateString("uk-UA")}`
                            : ""}
                        </span>
                      </span>
                      <span className="font-semibold">
                        {o.price ? formatPrice(o.price) : "—"}
                        {o.best && (
                          <span className="bg-success/15 text-success ml-2 rounded-full px-2 py-0.5 text-xs">
                            {t("pur.cheapest")}
                          </span>
                        )}
                      </span>
                    </span>
                  </ChooseButton>
                ))
              ) : (
                <ChooseButton line={line} fields={{ variant: p.variant }}>
                  {t("pur.takeWithoutSupplier")}
                </ChooseButton>
              )}
            </div>
          ))}
        </section>
      )}
      {options.items.length > 0 && (
        <section className="space-y-2">
          <h3 className="flex items-center gap-2 font-semibold">
            <Truck className="text-brand-600 size-5" aria-hidden /> {t("pur.supplierItems")}
          </h3>
          {options.items.map((i) => (
            <ChooseButton key={i.item} line={line} fields={{ item: i.item }}>
              <span className="flex flex-wrap items-baseline justify-between gap-2">
                <span>
                  <b>{i.name}</b>
                  <span className="text-muted text-sm">
                    {i.sku && ` · ${i.sku}`} · {i.supplier_name}
                  </span>
                </span>
                <span className="font-semibold">
                  {i.price
                    ? formatPrice(i.price)
                    : i.raw_price
                      ? `${Number(i.raw_price)} ${i.currency}`
                      : "—"}
                </span>
              </span>
            </ChooseButton>
          ))}
        </section>
      )}
      {nothing && <p className="text-muted text-base">{t("pur.nothingFound")}</p>}
      <Form method="post" preventScrollReset>
        <input type="hidden" name="intent" value="clear" />
        <input type="hidden" name="line" value={line.id} />
        <Button type="submit" variant="ghost">
          {t("pur.keepAsNote")}
        </Button>
      </Form>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const t = useT();
  const [done, setDone] = useState(false);
  return (
    <Button
      type="button"
      variant="secondary"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setDone(true));
      }}
    >
      {done ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
      {done ? t("pur.copied") : t("pur.copy")}
    </Button>
  );
}

function OrderView({ groups }: { groups: OrderGroup[] }) {
  const t = useT();
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <ButtonLink to="/seller/purchase" variant="secondary">
          ← {t("pur.backToList")}
        </ButtonLink>
        <Button type="button" variant="secondary" onClick={() => window.print()}>
          <Printer className="size-4" aria-hidden /> {t("pur.print")}
        </Button>
      </div>
      {groups.map((g) => (
        <section key={g.key} className="border-line space-y-3 rounded-2xl border bg-white p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">
              {g.key === "none" ? t("pur.groupNone") : g.supplier}
              {g.phone && (
                <a href={`tel:${g.phone}`} className="text-brand-600 ml-2 text-base font-normal">
                  {g.phone}
                </a>
              )}
            </h2>
            {g.key !== "none" && <span className="text-lg font-semibold">{formatPrice(g.total)}</span>}
          </div>
          <ol className="divide-line divide-y text-base">
            {g.lines.map((l, i) => (
              <li key={l.id} className="flex flex-wrap justify-between gap-2 py-2">
                <span>
                  {i + 1}. <b>{l.name}</b>
                  {l.sku && <span className="text-muted text-sm"> ({l.sku})</span>}
                </span>
                <span>
                  {formatQty(l.quantity)} {l.unit}
                  {l.total && <span className="text-muted"> · {formatPrice(l.total)}</span>}
                </span>
              </li>
            ))}
          </ol>
          {g.key === "none" ? (
            <p className="text-muted text-sm print:hidden">{t("pur.groupNoneHint")}</p>
          ) : (
            <div className="print:hidden">
              <CopyButton text={g.message} />
            </div>
          )}
        </section>
      ))}
      <Form
        method="post"
        className="print:hidden"
        onSubmit={(e) => {
          if (!confirm(t("pur.orderedConfirm"))) e.preventDefault();
        }}
      >
        <input type="hidden" name="intent" value="ordered" />
        <Button type="submit" size="lg" className="w-full">
          <Check className="size-5" aria-hidden /> {t("pur.ordered")}
        </Button>
      </Form>
    </div>
  );
}

export default function Purchase({ loaderData, actionData }: Route.ComponentProps) {
  const { list, options, lineId, view, order } = loaderData;
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const [many, setMany] = useState(false);
  const openId = actionData && "close" in actionData && actionData.close ? null : lineId;

  return (
    <div className="space-y-5 pb-24">
      <PageTitle subtitle={t("pur.subtitle")}>
        {view === "order" ? t("pur.orderTitle") : t("pur.nav")}
      </PageTitle>
      {actionData?.message && <Alert tone={actionData.ok ? "success" : "danger"}>{actionData.message}</Alert>}

      {view === "order" && order ? (
        order.groups.length ? (
          <OrderView groups={order.groups} />
        ) : (
          <EmptyState icon={ClipboardList} title={t("pur.empty")} />
        )
      ) : (
        <>
          <Form method="post" className="space-y-2" key={list.lines.length}>
            <input type="hidden" name="intent" value="add" />
            {many ? (
              <textarea
                name="texts"
                rows={6}
                autoFocus
                placeholder={t("pur.manyPlaceholder")}
                className="border-brand-500 focus:ring-brand-100 w-full rounded-2xl border-2 bg-white px-4 py-3 text-lg focus:ring-4 focus:outline-none"
              />
            ) : (
              <div className="flex gap-2">
                <input
                  name="texts"
                  autoFocus
                  autoComplete="off"
                  placeholder={t("pur.placeholder")}
                  aria-label={t("pur.placeholder")}
                  className="border-brand-500 focus:ring-brand-100 h-14 min-w-0 flex-1 rounded-2xl border-2 bg-white px-4 text-lg focus:ring-4 focus:outline-none"
                />
                <Button type="submit" size="lg" loading={busy} className="h-14 !px-6">
                  <Plus className="size-5" aria-hidden /> {t("pur.add")}
                </Button>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-3">
              {many && (
                <Button type="submit" size="lg" loading={busy}>
                  <Plus className="size-5" aria-hidden /> {t("pur.addAll")}
                </Button>
              )}
              <button
                type="button"
                onClick={() => setMany(!many)}
                className="text-brand-600 text-base underline underline-offset-2"
              >
                {many ? t("pur.oneByOne") : t("pur.pasteMany")}
              </button>
            </div>
          </Form>

          {list.lines.length === 0 ? (
            <EmptyState icon={ClipboardList} title={t("pur.empty")}>
              {t("pur.emptyText")}
            </EmptyState>
          ) : (
            <ul className="space-y-3">
              {list.lines.map((line) => (
                <LineCard
                  key={line.id}
                  line={line}
                  open={line.id === openId}
                  options={line.id === openId ? options : null}
                />
              ))}
            </ul>
          )}

          {list.lines.length > 0 && (
            <div className="border-line fixed inset-x-0 bottom-0 z-30 border-t bg-white/95 p-3 backdrop-blur lg:static lg:border-0 lg:bg-transparent lg:p-0">
              <ButtonLink to="/seller/purchase?view=order" size="lg" className="w-full text-lg">
                <Search className="size-5" aria-hidden /> {t("pur.assemble", { n: list.lines.length })}
              </ButtonLink>
            </div>
          )}
          <p className="text-muted text-sm">
            {t("pur.fromStockHint")}{" "}
            <Link to="/seller/stock" className="text-brand-600 underline">
              {t("wh.nav.stock")}
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
