import { clsx } from "clsx";
import { ExternalLink, Plus, Scale, Trash2 } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { data, Form, useActionData, useNavigation } from "react-router";

import { Pagination } from "~/components/Pagination";
import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, Badge, Button, Card, EmptyState, Input, PageTitle, Select } from "~/components/ui";
import { langFromRequest, LOCALE, makeT, tFromMatches, type TKey } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { formatDate, formatPrice, pluralize } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { Paginated, Supplier, SupplierOffer, SupplierPriceRow } from "~/lib/types";
import { formObject } from "~/lib/validation";

import type { Route } from "./+types/prices";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("pr.nav") }];

const CURRENCIES = ["UAH", "USD", "EUR"];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const filters = {
    search: q.get("search") ?? "",
    multi: q.get("multi") ?? "",
    sort: q.get("sort") ?? "spread",
  };
  const page = pageOf(request);
  const [rows, suppliers] = await Promise.all([
    paged(
      api.get<Paginated<SupplierPriceRow>>("/warehouse/supplier-prices/", { query: { ...filters, page } }),
    ),
    api.get<Supplier[]>("/warehouse/suppliers/"),
  ]);
  return { ...rows, page, pages: pagesOf(rows), filters, suppliers: suppliers.filter((s) => s.is_active) };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const v = formObject(await request.formData());
  const variant = Number(v.variant);
  try {
    if (v.intent === "delete") {
      await api.delete(`/warehouse/supplier-quotes/${Number(v.id)}/`);
      return { ok: true as const, variant, message: t("pr.quote.deleted") };
    }
    await api.post("/warehouse/supplier-quotes/", {
      variant,
      supplier: Number(v.supplier) || null,
      price: (v.price ?? "").replace(",", ".").replace(/\s/g, ""),
      currency: v.currency || "UAH",
      in_stock: v.in_stock === "1" ? true : v.in_stock === "0" ? false : null,
      note: v.note ?? "",
    });
    return { ok: true as const, variant, message: t("pr.quote.saved") };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, variant, message: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
}

function usePercent() {
  const lang = useLang();
  const fmt = new Intl.NumberFormat(LOCALE[lang], { maximumFractionDigits: 1 });
  return (value: number | null) => (value === null ? "—" : `${fmt.format(value)} %`);
}

export default function Prices({ loaderData, actionData }: Route.ComponentProps) {
  const { results, count, page, pages, filters, suppliers } = loaderData;
  const t = useT();
  const loading = useNavigation().state === "loading";

  return (
    <div className="space-y-4">
      <PageTitle subtitle={t("pr.subtitle")} help="prices">
        {t("pr.nav")}
      </PageTitle>

      <Form
        method="get"
        className="border-line flex flex-wrap items-end gap-3 rounded-2xl border bg-white p-4"
      >
        <label className="min-w-48 flex-1 space-y-1.5">
          <span className="text-sm font-medium">{t("catalog.search")}</span>
          <Input name="search" type="search" defaultValue={filters.search} placeholder={t("pr.search")} />
        </label>
        <label className="space-y-1.5">
          <span className="text-sm font-medium">{t("pr.sort")}</span>
          <Select name="sort" defaultValue={filters.sort}>
            <option value="spread">{t("pr.sort.spread")}</option>
            <option value="saving">{t("pr.sort.saving")}</option>
            <option value="name">{t("pr.sort.name")}</option>
          </Select>
        </label>
        <label className="flex h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="multi"
            value="1"
            defaultChecked={filters.multi === "1"}
            className="accent-brand-600 size-4"
          />
          {t("pr.multi")}
        </label>
        <Button type="submit">{t("common.show")}</Button>
      </Form>

      {actionData && <Alert tone={actionData.ok ? "success" : "danger"}>{actionData.message}</Alert>}

      {results.length === 0 ? (
        <EmptyState icon={Scale} title={t("pr.empty")}>
          {t("pr.emptyText")}
        </EmptyState>
      ) : (
        <div className={clsx("space-y-3 transition-opacity", loading && "opacity-60")}>
          <p className="text-muted text-sm">
            {count} {pluralize(count, t("plural.product"))}
          </p>
          {results.map((row) => (
            <PriceCard
              key={row.variant_id}
              row={row}
              suppliers={suppliers}
              open={actionData?.variant === row.variant_id}
            />
          ))}
          <Pagination page={page} pages={pages} />
        </div>
      )}
    </div>
  );
}

function Stat({ label, children, tone }: { label: string; children: ReactNode; tone?: "success" }) {
  return (
    <div>
      <p className="text-muted text-xs">{label}</p>
      <p className={clsx("font-semibold tabular-nums", tone === "success" && "text-success")}>{children}</p>
    </div>
  );
}

function PriceCard({
  row,
  suppliers,
  open,
}: {
  row: SupplierPriceRow;
  suppliers: Supplier[];
  open: boolean;
}) {
  const t = useT();
  const percent = usePercent();
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold">{row.name}</p>
          <p className="text-muted text-xs">{[row.code, row.barcode].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="muted">
            {row.suppliers} {pluralize(row.suppliers, t("pr.suppliers"))}
          </Badge>
          {row.product_id && (
            <Link
              to={`/seller/products/${row.product_id}`}
              className="text-brand-700 inline-flex items-center gap-1 text-sm hover:underline"
            >
              {t("pr.toProduct")} <ExternalLink className="size-3.5" aria-hidden />
            </Link>
          )}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label={t("pr.col.ourPrice")}>{formatPrice(row.price)}</Stat>
        <Stat label={t("pr.col.cost")}>{formatPrice(row.cost_price)}</Stat>
        <Stat label={t("pr.col.best")} tone="success">
          {row.best ? formatPrice(row.best.cost_uah) : "—"}
          {row.best && <span className="text-muted block text-xs font-normal">{row.best.supplier_name}</span>}
        </Stat>
        <Stat label={t("pr.col.spread")}>{percent(row.spread_pct)}</Stat>
        <Stat label={t("pr.col.margin")}>{percent(row.margin_pct)}</Stat>
        <Stat label={t("pr.col.saving")} tone={row.saving ? "success" : undefined}>
          {row.saving ? t("pr.perUnit", { sum: formatPrice(row.saving) }) : "—"}
        </Stat>
      </div>

      <details className="mt-3" open={open || undefined}>
        <summary className="text-brand-700 cursor-pointer text-sm font-medium">
          {t("pr.offers", { n: row.offers.length })}
        </summary>
        <div className="mt-3 space-y-4">
          <OffersTable row={row} />
          <QuoteForm variant={row.variant_id} suppliers={suppliers} />
        </div>
      </details>
    </Card>
  );
}

function OffersTable({ row }: { row: SupplierPriceRow }) {
  const t = useT();
  const lang = useLang();
  const number = new Intl.NumberFormat(LOCALE[lang], { maximumFractionDigits: 2 });
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th>{t("pr.col.supplier")}</Th>
            <Th align="right">{t("pr.col.purchase")}</Th>
            <Th align="right">{t("pr.col.rrp")}</Th>
            <Th>{t("pr.quote.stock")}</Th>
            <Th>{t("pr.col.source")}</Th>
            <Th>{t("pr.col.date")}</Th>
            <Th />
          </tr>
        </thead>
        <tbody>
          {row.offers.map((o, i) => (
            <tr key={`${o.kind}-${o.supplier_key}-${i}`} className={clsx(o.best && "bg-success/5")}>
              <Td className="font-medium">
                {o.supplier_name}
                {o.best && (
                  <span className="ml-2">
                    <Badge tone="success">{t("pr.best")}</Badge>
                  </span>
                )}
              </Td>
              <Td align="right" className="font-semibold whitespace-nowrap">
                {formatPrice(o.cost_uah)}
                {o.currency !== "UAH" && o.cost !== null && (
                  <span className="text-muted block text-xs font-normal">
                    {number.format(o.cost)} {o.currency}
                  </span>
                )}
              </Td>
              <Td align="right" className="text-muted whitespace-nowrap">
                {formatPrice(o.rrp_uah)}
              </Td>
              <Td>
                <Availability offer={o} />
              </Td>
              <Td className="text-sm">
                <Badge tone="muted">{t(`pr.kind.${o.kind}` as TKey)}</Badge>{" "}
                <span className="text-muted">
                  {o.kind === "invoice" && o.ref ? t("pr.invoiceNo", { n: o.ref }) : o.ref}
                </span>
                {o.url && (
                  <a href={o.url} target="_blank" rel="noreferrer noopener" className="text-brand-700 ml-1">
                    <ExternalLink className="inline size-3.5" aria-label={o.url} />
                  </a>
                )}
              </Td>
              <Td className="text-muted text-sm whitespace-nowrap">
                {o.date ? formatDate(o.date, lang) : "—"}
              </Td>
              <Td className="text-right">
                {o.quote_id && <DeleteQuote id={o.quote_id} variant={row.variant_id} />}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}

function Availability({ offer }: { offer: SupplierOffer }) {
  const t = useT();
  if (offer.available === false) return <Badge tone="danger">{t("pr.outOfStock")}</Badge>;
  if (offer.available === true)
    return (
      <span className="text-success text-sm">
        {offer.quantity !== null ? t("pr.qty", { qty: offer.quantity }) : t("pr.inStock")}
      </span>
    );
  return <span className="text-muted">—</span>;
}

function DeleteQuote({ id, variant }: { id: number; variant: number }) {
  const t = useT();
  return (
    <Form method="post" onSubmit={(e) => !confirm(t("pr.quote.deleteConfirm")) && e.preventDefault()}>
      <input type="hidden" name="intent" value="delete" />
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="variant" value={variant} />
      <Button type="submit" size="sm" variant="ghost" aria-label={t("pr.quote.delete")}>
        <Trash2 className="size-3.5" aria-hidden />
      </Button>
    </Form>
  );
}

function QuoteForm({ variant, suppliers }: { variant: number; suppliers: Supplier[] }) {
  const t = useT();
  const nav = useNavigation();
  const result = useActionData<typeof action>();
  const form = useRef<HTMLFormElement>(null);
  const busy = nav.state === "submitting" && Number(nav.formData?.get("variant")) === variant;
  // после сохранения форма пустая — можно сразу вносить цену следующего поставщика
  useEffect(() => {
    if (result?.ok && result.variant === variant) form.current?.reset();
  }, [result, variant]);
  if (suppliers.length === 0) return <p className="text-muted text-sm">{t("pr.noSuppliers")}</p>;
  return (
    <Form ref={form} method="post" className="bg-surface space-y-3 rounded-xl p-3">
      <p className="text-sm font-semibold">{t("pr.addQuote")}</p>
      <input type="hidden" name="intent" value="quote" />
      <input type="hidden" name="variant" value={variant} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <label className="space-y-1">
          <span className="text-xs font-medium">{t("pr.quote.supplier")}</span>
          <Select name="supplier" required defaultValue="">
            <option value="" disabled>
              {t("pr.quote.chooseSupplier")}
            </option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-1">
          <span className="text-xs font-medium">{t("pr.quote.price")}</span>
          <Input name="price" inputMode="decimal" required placeholder="1450" />
        </label>
        <label className="space-y-1">
          <span className="text-xs font-medium">{t("pr.quote.currency")}</span>
          <Select name="currency" defaultValue="UAH">
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-1">
          <span className="text-xs font-medium">{t("pr.quote.stock")}</span>
          <Select name="in_stock" defaultValue="">
            <option value="">{t("pr.quote.stockUnknown")}</option>
            <option value="1">{t("pr.inStock")}</option>
            <option value="0">{t("pr.outOfStock")}</option>
          </Select>
        </label>
        <label className="space-y-1">
          <span className="text-xs font-medium">{t("pr.quote.note")}</span>
          <Input name="note" maxLength={255} placeholder={t("pr.quote.notePlaceholder")} />
        </label>
      </div>
      <Button type="submit" size="sm" loading={busy}>
        <Plus className="size-4" aria-hidden /> {t("pr.quote.save")}
      </Button>
    </Form>
  );
}
