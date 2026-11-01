import { AlertTriangle, Clock } from "lucide-react";

import { StatCard, Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, PageTitle } from "~/components/ui";
import { tFromMatches, type TFunction, type TKey } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { formatDate, formatPrice, formatQty } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";
import type { SalesStats } from "~/lib/types";

import type { Route } from "./+types/stats";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("st.nav") }];

const PERIODS = [1, 7, 30, 90, 365] as const;

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const asked = Number(new URL(request.url).searchParams.get("days"));
  const days = PERIODS.find((p) => p === asked) ?? 30;
  return { stats: await api.get<SalesStats>("/orders/manage/stats/", { query: { days } }), days };
}

/** «+12 %» к прошлому периоду; null — сравнивать не с чем */
function change(now: string | number, before: string | number): number | null {
  const a = Number(now);
  const b = Number(before);
  if (!b) return null;
  return Math.round(((a - b) / b) * 100);
}

function ChangeHint({ now, before, t }: { now: string | number; before: string | number; t: TFunction }) {
  const pct = change(now, before);
  if (pct === null) return <>{t("st.noPrevious")}</>;
  const sign = pct > 0 ? "+" : "";
  return <>{t("st.vsPrevious", { pct: `${sign}${pct}` })}</>;
}

type Bar = { key: string; label: string; revenue: number; orders: number };

/** Год — по месяцам: 365 столбиков не читаются */
function bars(stats: SalesStats, lang: "uk" | "ru"): Bar[] {
  if (stats.period.days < 365) {
    return stats.by_day.map((d) => ({
      key: d.date,
      label: new Intl.DateTimeFormat(lang === "ru" ? "ru-UA" : "uk-UA", {
        day: "2-digit",
        month: "2-digit",
      }).format(new Date(`${d.date}T12:00:00`)),
      revenue: Number(d.revenue),
      orders: d.orders,
    }));
  }
  const months = new Map<string, Bar>();
  for (const d of stats.by_day) {
    const key = d.date.slice(0, 7);
    const bar = months.get(key) ?? {
      key,
      label: new Intl.DateTimeFormat(lang === "ru" ? "ru-UA" : "uk-UA", {
        month: "2-digit",
        year: "2-digit",
      }).format(new Date(`${key}-15T12:00:00`)),
      revenue: 0,
      orders: 0,
    };
    bar.revenue += Number(d.revenue);
    bar.orders += d.orders;
    months.set(key, bar);
  }
  return [...months.values()];
}

/** Подсказка у крайних столбиков прижата к краю, иначе вылезает за карточку */
function tipSide(i: number, n: number): string {
  if (i < 3) return "left-0";
  if (i > n - 4) return "right-0";
  return "left-1/2 -translate-x-1/2";
}

/** Выручка по дням: один ряд — один цвет, подпись при наведении, таблица — ниже. */
function RevenueChart({ data, t }: { data: Bar[]; t: TFunction }) {
  const max = Math.max(...data.map((d) => d.revenue), 0);
  if (!max) return <p className="text-muted text-sm">{t("st.noSales")}</p>;
  const step = Math.ceil(data.length / 6); // подписи под осью — не больше 6–7
  return (
    <div>
      <p className="text-muted mb-2 text-xs tabular-nums">{t("st.max", { value: formatPrice(max) })}</p>
      <div
        className="border-line flex h-48 items-end gap-[2px] border-b"
        role="img"
        aria-label={t("st.chartAria", { days: data.length })}
      >
        {data.map((d, i) => (
          <div
            key={d.key}
            tabIndex={0}
            className="group relative flex h-full min-w-0 flex-1 items-end outline-none"
            aria-label={`${d.label}: ${formatPrice(d.revenue)}, ${t("st.ordersN", { n: d.orders })}`}
          >
            <div
              className="bg-brand-600 group-hover:bg-brand-700 group-focus:bg-brand-700 w-full rounded-t-[4px]"
              style={{ height: d.revenue ? `${Math.max((d.revenue / max) * 100, 2)}%` : 0 }}
            />
            <div
              className={`bg-ink pointer-events-none absolute bottom-full z-10 mb-1 hidden rounded-lg px-2 py-1 text-xs whitespace-nowrap text-white group-hover:block group-focus:block ${tipSide(i, data.length)}`}
            >
              {d.label} · {formatPrice(d.revenue)} · {t("st.ordersN", { n: d.orders })}
            </div>
          </div>
        ))}
      </div>
      <div className="text-muted mt-1 flex gap-[2px] text-[11px] tabular-nums">
        {data.map((d, i) => (
          <span key={d.key} className="min-w-0 flex-1 overflow-visible text-center whitespace-nowrap">
            {i % step === 0 ? d.label : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function SellerStats({ loaderData }: Route.ComponentProps) {
  const { stats, days } = loaderData;
  const t = useT();
  const lang = useLang();
  const chart = bars(stats, lang);
  return (
    <div className="space-y-6">
      <PageTitle>{t("st.title")}</PageTitle>

      <nav className="flex flex-wrap gap-2" aria-label={t("st.period")}>
        {PERIODS.map((p) => (
          <Link
            key={p}
            to={`/seller/stats?days=${p}`}
            className={`rounded-full border px-3 py-1.5 text-sm ${p === days ? "border-brand-600 bg-brand-600 text-white" : "border-line hover:border-brand-500 bg-white"}`}
          >
            {t(`st.days.${p}` as TKey)}
          </Link>
        ))}
      </nav>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatCard
          label={t("st.revenue")}
          value={formatPrice(Math.round(Number(stats.revenue)))}
          hint={<ChangeHint now={stats.revenue} before={stats.previous.revenue} t={t} />}
        />
        <StatCard
          label={t("st.orders")}
          value={stats.orders}
          hint={<ChangeHint now={stats.orders} before={stats.previous.orders} t={t} />}
        />
        <StatCard label={t("st.avgCheck")} value={formatPrice(Math.round(Number(stats.avg_check)))} />
        <StatCard
          label={t("st.profit")}
          value={formatPrice(Math.round(Number(stats.profit)))}
          hint={
            stats.profit_coverage < 100
              ? t("st.profitPartial", { pct: stats.profit_coverage })
              : t("st.profitHint")
          }
        />
        <StatCard label={t("st.units")} value={formatQty(stats.units)} />
        <StatCard label={t("st.canceled")} value={stats.canceled} />
      </div>

      {stats.on_order_open.lines > 0 && (
        <Alert>
          <span className="flex flex-wrap items-center gap-2">
            <Clock className="size-4" aria-hidden />
            {t("st.onOrder", { lines: stats.on_order_open.lines, orders: stats.on_order_open.orders })}
            <Link to="/seller/orders" className="font-semibold underline">
              {t("ord.nav")}
            </Link>
          </span>
        </Alert>
      )}

      {days > 1 && (
        <section className="border-line space-y-3 rounded-2xl border bg-white p-4">
          <h2 className="font-semibold">{t(days >= 365 ? "st.chartMonths" : "st.chartDays")}</h2>
          <RevenueChart data={chart} t={t} />
          <details>
            <summary className="text-brand-700 cursor-pointer text-sm">{t("st.asTable")}</summary>
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>{t("st.col.date")}</Th>
                    <Th align="right">{t("st.orders")}</Th>
                    <Th align="right">{t("st.revenue")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {chart
                    .filter((d) => d.orders)
                    .map((d) => (
                      <tr key={d.key}>
                        <Td>{d.label}</Td>
                        <Td align="right">{d.orders}</Td>
                        <Td align="right" className="whitespace-nowrap">
                          {formatPrice(d.revenue)}
                        </Td>
                      </tr>
                    ))}
                </tbody>
              </Table>
            </TableWrap>
          </details>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("st.topProducts")}</h2>
          {stats.top_products.length ? (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>{t("st.col.product")}</Th>
                    <Th align="right">{t("st.col.qty")}</Th>
                    <Th align="right">{t("st.revenue")}</Th>
                    <Th align="right">{t("st.profit")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top_products.map((p) => (
                    <tr key={p.variant_id}>
                      <Td>
                        {p.product_id ? (
                          <Link
                            to={`/seller/products/${p.product_id}`}
                            className="text-brand-700 hover:underline"
                          >
                            {p.name}
                          </Link>
                        ) : (
                          p.name
                        )}
                      </Td>
                      <Td align="right">{formatQty(p.qty)}</Td>
                      <Td align="right" className="whitespace-nowrap">
                        {formatPrice(p.revenue)}
                      </Td>
                      <Td align="right" className="whitespace-nowrap">
                        {formatPrice(p.profit)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          ) : (
            <p className="text-muted text-sm">{t("st.noSales")}</p>
          )}
        </section>

        {stats.by_channel.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">{t("st.byChannel")}</h2>
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>{t("st.col.channel")}</Th>
                    <Th align="right">{t("st.orders")}</Th>
                    <Th align="right">{t("st.revenue")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {stats.by_channel.map((c) => (
                    <tr key={c.channel}>
                      <Td>{c.label}</Td>
                      <Td align="right">{c.orders}</Td>
                      <Td align="right" className="whitespace-nowrap">
                        {formatPrice(c.revenue)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          </section>
        )}

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("st.topCategories")}</h2>
          {stats.top_categories.length ? (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>{t("st.col.category")}</Th>
                    <Th align="right">{t("st.col.qty")}</Th>
                    <Th align="right">{t("st.revenue")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top_categories.map((c) => (
                    <tr key={c.category}>
                      <Td>{c.category}</Td>
                      <Td align="right">{formatQty(c.qty)}</Td>
                      <Td align="right" className="whitespace-nowrap">
                        {formatPrice(c.revenue)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          ) : (
            <p className="text-muted text-sm">{t("st.noSales")}</p>
          )}
        </section>
      </div>

      {stats.low_stock.length > 0 && (
        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <AlertTriangle className="text-warning size-5" aria-hidden /> {t("st.lowStock")}
          </h2>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>{t("st.col.product")}</Th>
                  <Th align="right">{t("st.col.available")}</Th>
                  <Th align="right">{t("st.col.sold")}</Th>
                </tr>
              </thead>
              <tbody>
                {stats.low_stock.map((v) => (
                  <tr key={v.variant_id}>
                    <Td>{v.name}</Td>
                    <Td align="right">{formatQty(v.available)}</Td>
                    <Td align="right">{formatQty(v.sold)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t("st.deadStock")}</h2>
        <p className="text-muted text-sm">
          {stats.dead_stock.count
            ? t("st.deadSummary", { n: stats.dead_stock.count, value: formatPrice(stats.dead_stock.value) })
            : t("st.deadNone")}
        </p>
        {stats.dead_stock.items.length > 0 && (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>{t("st.col.product")}</Th>
                  <Th align="right">{t("st.col.stock")}</Th>
                  <Th align="right">{t("st.col.value")}</Th>
                  <Th align="right">{t("st.col.lastSold")}</Th>
                </tr>
              </thead>
              <tbody>
                {stats.dead_stock.items.map((v) => (
                  <tr key={v.variant_id}>
                    <Td>{v.name}</Td>
                    <Td align="right">{formatQty(v.stock)}</Td>
                    <Td align="right" className="whitespace-nowrap">
                      {formatPrice(v.value)}
                    </Td>
                    <Td align="right">{v.last_sold ? formatDate(v.last_sold, lang) : t("st.never")}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </section>
    </div>
  );
}
