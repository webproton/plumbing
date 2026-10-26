import { AlertTriangle, FileText, LifeBuoy, Scale } from "lucide-react";

import { StatCard, Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, ButtonLink, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { formatDate, formatPrice, formatQty } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";
import type { WarehouseDashboard } from "~/lib/types";

import type { Route } from "./+types/index";
import { MovementBadge } from "./movements";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("wh.nav.overview") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  return { dash: await api.get<WarehouseDashboard>("/warehouse/dashboard/") };
}

export default function SellerHome({ loaderData }: Route.ComponentProps) {
  const { dash } = loaderData;
  const t = useT();
  const lang = useLang();
  return (
    <div className="space-y-6">
      <PageTitle>{t("wh.nav.overview")}</PageTitle>

      {dash.positions === 0 && (
        <Alert>
          {t("help.firstTime")}{" "}
          <Link to="/seller/help" className="font-semibold underline">
            {t("help.openGuide")}
          </Link>
        </Alert>
      )}

      {dash.documents_need_review > 0 && (
        <Alert tone="danger">
          <span className="flex flex-wrap items-center gap-2">
            <AlertTriangle className="size-4" aria-hidden />
            {t("wh.dash.needReview", { n: dash.documents_need_review })}
            <Link to="/seller/documents" className="font-semibold underline">
              {t("wh.dash.open")}
            </Link>
          </span>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label={t("wh.dash.positions")} value={dash.positions} />
        <StatCard label={t("wh.dash.units")} value={formatQty(dash.units)} />
        <StatCard label={t("wh.dash.value")} value={formatPrice(dash.value)} hint={t("wh.dash.valueHint")} />
        <StatCard label={t("wh.dash.reserved")} value={formatQty(dash.reserved_units)} hint={t("wh.dash.reservedHint")} />
      </div>

      <div className="flex flex-wrap gap-3">
        <ButtonLink to="/seller/documents" variant="secondary">
          <FileText className="size-4" aria-hidden /> {t("wh.dash.uploadInvoice")}
          {dash.documents_pending > 0 && ` (${dash.documents_pending})`}
        </ButtonLink>
        <ButtonLink to="/seller/scanner" variant="secondary">
          {t("wh.nav.scanner")}
        </ButtonLink>
        <ButtonLink to="/seller/operations" variant="secondary">
          {t("wh.nav.operations")}
        </ButtonLink>
        <ButtonLink to="/seller/prices" variant="secondary">
          <Scale className="size-4" aria-hidden /> {t("pr.nav")}
        </ButtonLink>
        <ButtonLink to="/seller/help" variant="ghost">
          <LifeBuoy className="size-4" aria-hidden /> {t("help.nav")}
        </ButtonLink>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t("wh.dash.recent")}</h2>
        <TableWrap>
          <Table>
            <thead>
              <tr>
                <Th>{t("wh.col.date")}</Th>
                <Th>{t("wh.col.type")}</Th>
                <Th>{t("wh.col.product")}</Th>
                <Th>{t("wh.col.warehouse")}</Th>
                <Th align="right">{t("wh.col.qty")}</Th>
              </tr>
            </thead>
            <tbody>
              {dash.recent_movements.length === 0 && (
                <tr>
                  <Td colSpan={5} className="py-8 text-center text-muted">
                    {t("wh.empty.movements")}
                  </Td>
                </tr>
              )}
              {dash.recent_movements.map((m) => (
                <tr key={m.id}>
                  <Td className="whitespace-nowrap text-muted">{formatDate(m.created_at, lang)}</Td>
                  <Td>
                    <MovementBadge type={m.movement_type} />
                  </Td>
                  <Td>{m.variant_name}</Td>
                  <Td>{m.warehouse_name}</Td>
                  <Td align="right">{formatQty(m.quantity)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      </section>
    </div>
  );
}
