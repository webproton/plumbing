import { ClipboardList } from "lucide-react";
import { Form, useNavigation } from "react-router";

import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Pagination } from "~/components/Pagination";
import { Badge, Button, EmptyState, Input, PageTitle, Select } from "~/components/ui";
import { tFromMatches, type TKey } from "~/i18n";
import { useLang, useT } from "~/i18n/react";
import { formatDate, formatPrice, formatQty, pluralize } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { MovementRow, MovementType, Paginated } from "~/lib/types";

import type { Route } from "./+types/movements";
import { useSellerMe } from "./layout";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("wh.nav.movements") }];

const TYPES: MovementType[] = [
  "in",
  "out",
  "return_in",
  "return_out",
  "transfer_in",
  "transfer_out",
  "adjustment",
  "adjustment_out",
  "in_reversal",
];
const OUTGOING = new Set<MovementType>(["out", "return_out", "transfer_out", "adjustment_out", "in_reversal"]);

export function MovementBadge({ type }: { type: MovementType }) {
  const t = useT();
  return <Badge tone={OUTGOING.has(type) ? "danger" : "success"}>{t(`wh.mt.${type}` as TKey)}</Badge>;
}

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const filters = {
    search: q.get("search") ?? "",
    movement_type: q.get("movement_type") ?? "",
    warehouse: q.get("warehouse") ?? "",
    variant: q.get("variant") ?? "",
    inventory_document: q.get("document") ?? "",
  };
  const page = pageOf(request);
  const data = await paged(api.get<Paginated<MovementRow>>("/warehouse/stock-movements/", { query: { ...filters, page } }));
  return { ...data, page, pages: pagesOf(data), filters };
}

export default function Movements({ loaderData }: Route.ComponentProps) {
  const { results, count, page, pages, filters } = loaderData;
  const me = useSellerMe();
  const t = useT();
  const lang = useLang();
  const loading = useNavigation().state === "loading";

  return (
    <div className="space-y-4">
      <PageTitle subtitle={`${count} ${pluralize(count, t("plural.record"))} · ${t("wh.movements.immutable")}`}>
        {t("wh.nav.movements")}
      </PageTitle>

      <Form method="get" className="flex flex-wrap items-end gap-3 rounded-2xl border border-line bg-white p-4">
        {filters.variant && <input type="hidden" name="variant" value={filters.variant} />}
        <label className="min-w-48 flex-1 space-y-1.5">
          <span className="text-sm font-medium">{t("catalog.search")}</span>
          <Input name="search" type="search" defaultValue={filters.search} placeholder={t("wh.movements.searchPlaceholder")} />
        </label>
        <label className="space-y-1.5">
          <span className="text-sm font-medium">{t("wh.col.type")}</span>
          <Select name="movement_type" defaultValue={filters.movement_type}>
            <option value="">{t("wh.filter.allTypes")}</option>
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`wh.mt.${type}` as TKey)}
              </option>
            ))}
          </Select>
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
        <Button type="submit">{t("common.show")}</Button>
      </Form>

      {results.length === 0 ? (
        <EmptyState icon={ClipboardList} title={t("wh.empty.movements")} />
      ) : (
        <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>{t("wh.col.date")}</Th>
                  <Th>{t("wh.col.type")}</Th>
                  <Th>{t("wh.col.product")}</Th>
                  <Th>{t("wh.col.warehouse")}</Th>
                  <Th align="right">{t("wh.col.qty")}</Th>
                  <Th align="right">{t("wh.col.price")}</Th>
                  <Th>{t("wh.col.document")}</Th>
                  <Th>{t("wh.col.user")}</Th>
                </tr>
              </thead>
              <tbody>
                {results.map((m) => {
                  const out = OUTGOING.has(m.movement_type);
                  return (
                    <tr key={m.id} className="hover:bg-surface">
                      <Td className="whitespace-nowrap text-muted">{formatDate(m.created_at, lang)}</Td>
                      <Td>
                        <MovementBadge type={m.movement_type} />
                      </Td>
                      <Td>
                        {m.variant_name}
                        {m.comment && <p className="max-w-xs truncate text-xs text-muted">{m.comment}</p>}
                      </Td>
                      <Td>{m.warehouse_name}</Td>
                      <Td align="right" className={`font-semibold ${out ? "text-danger" : "text-success"}`}>
                        {out ? "−" : "+"}
                        {formatQty(m.quantity)}
                      </Td>
                      <Td align="right">{formatPrice(m.price_per_unit)}</Td>
                      <Td className="text-muted">{m.document_number ?? m.supplier_name ?? "—"}</Td>
                      <Td className="text-muted">{m.created_by_email ?? "—"}</Td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </TableWrap>
          <Pagination page={page} pages={pages} />
        </div>
      )}
    </div>
  );
}
