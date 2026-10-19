import { ShoppingBag } from "lucide-react";
import { Form, useSearchParams } from "react-router";

import { Pagination } from "~/components/Pagination";
import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Badge, Button, EmptyState, Input, PageTitle } from "~/components/ui";
import { tFromMatches, type TKey } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { formatDateTime, formatPrice, paymentTone, pluralize, statusTone } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { ManageOrderRow, OrderStatus, Paginated } from "~/lib/types";

import type { Route } from "./+types/orders";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("ord.nav") }];

const TABS: (OrderStatus | "all")[] = [
  "in_processing",
  "delivering",
  "delivered",
  "completed",
  "canceled",
  "all",
];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const tab = TABS.find((s) => s === q.get("status")) ?? "in_processing";
  const page = pageOf(request);
  const [orders, counts] = await Promise.all([
    paged(
      api.get<Paginated<ManageOrderRow>>("/orders/manage/", {
        query: { status: tab === "all" ? undefined : tab, q: q.get("q") || undefined, page },
      }),
    ),
    api.get<Partial<Record<OrderStatus, number>>>("/orders/manage/counts/"),
  ]);
  return { ...orders, tab, counts, page, pages: pagesOf(orders) };
}

export default function Orders({ loaderData }: Route.ComponentProps) {
  const { results, tab, counts, page, pages } = loaderData;
  const t = useT();
  const lang = useLang();
  const [params] = useSearchParams();
  const total = Object.values(counts).reduce((a, b) => a + (b ?? 0), 0);

  const tabHref = (s: string) => {
    const next = new URLSearchParams(params);
    next.delete("page");
    next.set("status", s);
    return `/seller/orders?${next}`;
  };

  return (
    <div className="space-y-5">
      <PageTitle subtitle={t("ord.subtitle")}>{t("ord.nav")}</PageTitle>
      <nav className="flex flex-wrap gap-2" aria-label={t("catalog.filters")}>
        {TABS.map((s) => {
          const n = s === "all" ? total : (counts[s] ?? 0);
          return (
            <Link
              key={s}
              to={tabHref(s)}
              className={`rounded-full border px-3 py-1 text-sm ${s === tab ? "border-brand-500 bg-brand-50 text-brand-700 font-medium" : "border-line hover:border-brand-500 bg-white"}`}
            >
              {t(`ord.tab.${s}` as TKey)}
              {n > 0 && <span className="text-muted ml-1.5">{n}</span>}
            </Link>
          );
        })}
      </nav>
      <Form method="get" className="flex flex-wrap items-center gap-3">
        <input type="hidden" name="status" value={tab} />
        <Input
          name="q"
          defaultValue={params.get("q") ?? ""}
          placeholder={t("ord.search")}
          className="w-72 py-2"
          aria-label={t("nav.search")}
        />
        <Button type="submit" variant="secondary" size="sm">
          {t("common.show")}
        </Button>
      </Form>

      {results.length === 0 ? (
        <EmptyState icon={ShoppingBag} title={t("ord.empty")} />
      ) : (
        <>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>{t("ord.col.order")}</Th>
                  <Th>{t("ord.col.customer")}</Th>
                  <Th>{t("ord.col.delivery")}</Th>
                  <Th align="right">{t("ord.col.total")}</Th>
                  <Th>{t("ord.col.payment")}</Th>
                  <Th>{t("ord.col.status")}</Th>
                </tr>
              </thead>
              <tbody>
                {results.map((o) => (
                  <tr key={o.id} className="hover:bg-surface align-top">
                    <Td>
                      <Link
                        to={`/seller/orders/${o.id}`}
                        className="text-brand-700 font-semibold hover:underline"
                      >
                        №{o.id}
                      </Link>
                      <p className="text-muted text-xs whitespace-nowrap">
                        {formatDateTime(o.creation_date, lang)}
                      </p>
                    </Td>
                    <Td>
                      <p className="font-medium">{o.customer_name}</p>
                      <p className="text-muted text-xs">{o.phone_number}</p>
                    </Td>
                    <Td className="text-muted max-w-64 text-sm">{o.address}</Td>
                    <Td align="right" className="whitespace-nowrap">
                      {formatPrice(o.total_price)}
                      <p className="text-muted text-xs">
                        {o.items_count} {pluralize(o.items_count, t("ord.items"))}
                      </p>
                    </Td>
                    <Td>
                      <Badge tone={paymentTone(o.payment_status)}>{o.payment_status_display}</Badge>
                    </Td>
                    <Td>
                      <Badge tone={statusTone(o.status_order)}>{o.status_display}</Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
          <Pagination page={page} pages={pages} />
        </>
      )}
    </div>
  );
}
