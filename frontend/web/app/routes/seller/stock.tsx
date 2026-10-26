import { PackageSearch } from "lucide-react";
import { Form, useNavigation } from "react-router";

import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Pagination } from "~/components/Pagination";
import { Button, EmptyState, Input, PageTitle, Select } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
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
  const data = await paged(api.get<Paginated<StockRow>>("/warehouse/balances/", { query: { ...filters, page } }));
  return { ...data, page, pages: pagesOf(data), filters };
}

export default function Stock({ loaderData }: Route.ComponentProps) {
  const { results, count, page, pages, filters } = loaderData;
  const me = useSellerMe();
  const t = useT();
  const loading = useNavigation().state === "loading";

  return (
    <div className="space-y-4">
      <PageTitle subtitle={`${count} ${pluralize(count, t("plural.position"))}`} help="stock">{t("wh.nav.stock")}</PageTitle>

      <Form method="get" className="flex flex-wrap items-end gap-3 rounded-2xl border border-line bg-white p-4">
        <label className="min-w-48 flex-1 space-y-1.5">
          <span className="text-sm font-medium">{t("catalog.search")}</span>
          <Input name="search" type="search" defaultValue={filters.search} placeholder={t("catalog.searchPlaceholder")} />
        </label>
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
          <input type="checkbox" name="in_stock" value="1" defaultChecked={filters.in_stock === "1"} className="size-4 accent-brand-600" />
          {t("wh.filter.inStockOnly")}
        </label>
        <Button type="submit">{t("common.show")}</Button>
      </Form>

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
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-surface">
                    <Td>
                      <Link to={`/seller/movements?variant=${r.variant}`} className="font-medium hover:text-brand-600">
                        {r.variant_name}
                      </Link>
                      {r.barcode && <p className="text-xs text-muted">{r.barcode}</p>}
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
