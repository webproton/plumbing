import { PackageSearch, ShoppingCart } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Pagination } from "~/components/Pagination";
import { Alert, applyOnPick, EmptyState, PageTitle, SearchBox, Select } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { formatPrice, formatQty, pluralize } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { Paginated, StockRow } from "~/lib/types";

import type { Route } from "./+types/stock";
import { useSellerMe } from "./layout";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("wh.nav.stock") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const filters = {
    search: q.get("search") ?? "",
    warehouse: q.get("warehouse") ?? "",
    in_stock: q.get("in_stock") ?? "",
    ordering: q.get("ordering") ?? "",
  };
  const page = pageOf(request);
  const data = await paged(
    api.get<Paginated<StockRow>>("/warehouse/balances/", { query: { ...filters, page } }),
  );
  return { ...data, page, pages: pagesOf(data), filters };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  try {
    await api.post("/warehouse/purchase/lines/", { variants: [Number(form.get("variant"))] });
    return { ok: true as const, message: t("pur.addedFromStock", { name: String(form.get("name") ?? "") }) };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, message: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
}

export default function Stock({ loaderData, actionData }: Route.ComponentProps) {
  const { results, count, page, pages, filters } = loaderData;
  const me = useSellerMe();
  const t = useT();
  const loading = useNavigation().state === "loading";

  return (
    <div className="space-y-4">
      <PageTitle subtitle={`${count} ${pluralize(count, t("plural.position"))}`} help="stock">
        {t("wh.nav.stock")}
      </PageTitle>

      <Form
        method="get"
        onChange={applyOnPick}
        className="border-line flex flex-wrap items-end gap-3 rounded-2xl border bg-white p-4"
      >
        <div className="min-w-64 flex-1 space-y-1.5">
          <span className="text-sm font-medium">{t("catalog.search")}</span>
          <SearchBox
            name="search"
            defaultValue={filters.search}
            placeholder={t("catalog.searchPlaceholder")}
            aria-label={t("catalog.search")}
          />
        </div>
        <label className="space-y-1.5">
          <span className="text-sm font-medium">{t("wh.col.warehouse")}</span>
          <Select name="warehouse" defaultValue={filters.warehouse}>
            <option value="">{t("wh.filter.allWarehouses")}</option>
            {me.warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        </label>
        <label className="space-y-1.5">
          <span className="text-sm font-medium">{t("catalog.sort")}</span>
          <Select name="ordering" defaultValue={filters.ordering}>
            <option value="">{t("catalog.sort.name")}</option>
            <option value="-quantity">{t("wh.sort.qtyDesc")}</option>
            <option value="quantity">{t("wh.sort.qtyAsc")}</option>
          </Select>
        </label>
        <label className="flex h-11 items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="in_stock"
            value="1"
            defaultChecked={filters.in_stock === "1"}
            className="accent-brand-600 size-4"
          />
          {t("wh.filter.inStockOnly")}
        </label>
      </Form>

      {actionData?.message && (
        <Alert tone={actionData.ok ? "success" : "danger"}>
          {actionData.message}{" "}
          {actionData.ok && (
            <Link to="/seller/purchase" className="font-semibold underline">
              {t("pur.openList")}
            </Link>
          )}
        </Alert>
      )}

      {results.length === 0 ? (
        <EmptyState icon={PackageSearch} title={t("wh.empty.stock")} />
      ) : (
        <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>{t("wh.col.product")}</Th>
                  <Th>{t("wh.col.sku")}</Th>
                  <Th>{t("wh.col.warehouse")}</Th>
                  <Th align="right">{t("wh.col.qty")}</Th>
                  <Th align="right">{t("wh.col.reserved")}</Th>
                  <Th align="right">{t("wh.col.cost")}</Th>
                  <Th align="right">{t("wh.col.value")}</Th>
                  <Th>
                    <span className="sr-only">{t("pur.nav")}</span>
                  </Th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-surface">
                    <Td>
                      <Link
                        to={`/seller/movements?variant=${r.variant}`}
                        className="hover:text-brand-600 font-medium"
                      >
                        {r.variant_name}
                      </Link>
                      {r.barcode && <p className="text-muted text-xs">{r.barcode}</p>}
                    </Td>
                    <Td className="text-muted">{r.sku ?? "—"}</Td>
                    <Td>{r.warehouse_name}</Td>
                    <Td align="right" className="font-semibold">
                      {formatQty(r.quantity)}
                    </Td>
                    <Td align="right" className="text-muted">
                      {Number(r.reserved) > 0 ? formatQty(r.reserved) : "—"}
                    </Td>
                    <Td align="right">{formatPrice(r.cost_price)}</Td>
                    <Td align="right">{formatPrice(r.value)}</Td>
                    <Td>
                      <Form method="post" preventScrollReset>
                        <input type="hidden" name="variant" value={r.variant} />
                        <input type="hidden" name="name" value={r.variant_name} />
                        <button
                          type="submit"
                          className="border-brand-500 text-brand-700 hover:bg-brand-50 inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium whitespace-nowrap"
                        >
                          <ShoppingCart className="size-4" aria-hidden /> {t("pur.toList")}
                        </button>
                      </Form>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
          <Pagination page={page} pages={pages} />
        </div>
      )}
    </div>
  );
}
