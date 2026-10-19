import { CheckCircle2, Loader2, X } from "lucide-react";
import { data, Form, useNavigation, useSearchParams } from "react-router";

import { Pagination } from "~/components/Pagination";
import { ACTIVE_RUN, RunStatusBadge, usePolling } from "~/components/seller/imports";
import { StatCard, Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, Badge, Button, Card, Field, PageTitle, Select } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TKey } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError } from "~/lib/api.server";
import { formatPrice, formatQty } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { ImportRow, ImportRun, Paginated, RowAction } from "~/lib/types";

import type { Route } from "./+types/import-run";
import { useSellerMe } from "./layout";

export const meta: Route.MetaFunction = ({ params, matches }) => [
  { title: tFromMatches(matches)("imp.run.title", { id: params.id ?? "" }) },
];

const FILTERS = ["all", "errors", "create", "update", "warnings"] as const;
type Filter = (typeof FILTERS)[number];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const filter: Filter = FILTERS.find((f) => f === q.get("filter")) ?? "all";
  const page = pageOf(request);
  try {
    const [run, rows] = await Promise.all([
      api.get<ImportRun>(`/imports/runs/${params.id}/`),
      paged(api.get<Paginated<ImportRow>>(`/imports/runs/${params.id}/rows/`, { query: { filter, page } })),
    ]);
    return { run, rows, filter, page, pages: pagesOf(rows) };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data("Not Found", { status: 404 });
    throw e;
  }
}

export async function action({ request, params, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  try {
    if (form.get("intent") === "cancel") {
      await api.delete(`/imports/runs/${params.id}/`);
      return localRedirect(request, "/seller/import");
    }
    await api.post(`/imports/runs/${params.id}/apply/`, {
      warehouse: Number(form.get("warehouse")) || null,
      publish: form.get("publish") === "1",
    });
    return { ok: true as const, error: null };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, error: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
}

const ACTION_TONE: Record<RowAction, "success" | "info" | "danger"> = {
  create: "success",
  update: "info",
  error: "danger",
};

function RowLine({ row }: { row: ImportRow }) {
  const t = useT();
  const d = row.data;
  return (
    <tr className="align-top">
      <Td className="text-muted tabular-nums">{row.row}</Td>
      <Td>
        <Badge tone={row.result === "failed" ? "danger" : ACTION_TONE[row.action]}>
          {t(`imp.action.${row.action}` as TKey)}
        </Badge>
      </Td>
      <Td className="whitespace-nowrap">{d.sku || d.barcode || "—"}</Td>
      <Td className="min-w-48">
        {d.name || "—"}
        {d.variant && <span className="text-muted"> · {d.variant}</span>}
        {d.category && <p className="text-muted text-xs">{d.category}</p>}
      </Td>
      <Td align="right" className="whitespace-nowrap">
        {d.price ? formatPrice(d.price) : "—"}
        {d.old_price && <p className="text-muted text-xs line-through">{formatPrice(d.old_price)}</p>}
      </Td>
      <Td align="right">{d.quantity != null ? formatQty(d.quantity) : "—"}</Td>
      <Td className="min-w-56 text-sm">
        {row.errors.map((m) => (
          <p key={m} className="text-danger">
            {m}
          </p>
        ))}
        {row.warnings.map((m) => (
          <p key={m} className="text-amber-700">
            {m}
          </p>
        ))}
      </Td>
    </tr>
  );
}

export default function ImportRunPage({ loaderData, actionData }: Route.ComponentProps) {
  const { run, rows, filter, page, pages } = loaderData;
  const t = useT();
  const me = useSellerMe();
  const [params] = useSearchParams();
  const busy = useNavigation().state === "submitting";
  const s = run.stats;
  const applicable = (s.create ?? 0) + (s.update ?? 0);
  const active = ACTIVE_RUN.includes(run.status);
  usePolling(active);

  const filterHref = (f: Filter) => {
    const next = new URLSearchParams(params);
    next.delete("page");
    if (f === "all") next.delete("filter");
    else next.set("filter", f);
    const qs = next.toString();
    return `/seller/import/${run.id}${qs ? `?${qs}` : ""}`;
  };
  const columns = Object.values(s.columns ?? {}).join(", ");

  return (
    <div className="space-y-6">
      <div>
        <Link to="/seller/import" className="text-brand-700 text-sm hover:underline">
          {t("imp.run.back")}
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <PageTitle subtitle={run.file_name}>{t("imp.run.title", { id: run.id })}</PageTitle>
          <RunStatusBadge status={run.status} />
        </div>
      </div>

      {run.stats.result ? (
        <div className="grid gap-3 sm:grid-cols-4">
          <StatCard label={t("imp.res.created")} value={run.stats.result.created} />
          <StatCard label={t("imp.res.updated")} value={run.stats.result.updated} />
          <StatCard label={t("imp.res.failed")} value={run.stats.result.failed} />
          <StatCard label={t("imp.res.stock")} value={run.stats.result.stock} />
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-5">
          <StatCard label={t("imp.stat.rows")} value={s.rows ?? 0} />
          <StatCard label={t("imp.stat.create")} value={s.create ?? 0} />
          <StatCard label={t("imp.stat.update")} value={s.update ?? 0} />
          <StatCard label={t("imp.stat.errors")} value={s.errors ?? 0} />
          <StatCard label={t("imp.stat.stock")} value={s.stock ?? 0} />
        </div>
      )}
      {columns && <p className="text-muted text-sm">{t("imp.run.columns", { columns })}</p>}

      {run.status === "preview" && (
        <Card className="space-y-4 p-5">
          <p className="text-sm">{applicable > 0 ? t("imp.run.previewText") : t("imp.run.nothing")}</p>
          {actionData?.error && <Alert tone="danger">{actionData.error}</Alert>}
          <div className="flex flex-wrap items-end gap-4">
            <Form method="post" className="flex flex-wrap items-end gap-4">
              {(s.stock ?? 0) > 0 && (
                <div className="w-56">
                  <Field label={t("imp.upload.warehouse")}>
                    {(p) => (
                      <Select {...p} name="warehouse" defaultValue={run.options.warehouse_id ?? ""} required>
                        <option value="">—</option>
                        {me.warehouses.map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.name}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                </div>
              )}
              <label className="flex items-center gap-2 pb-3 text-sm">
                <input
                  type="checkbox"
                  name="publish"
                  value="1"
                  defaultChecked={run.options.publish}
                  className="accent-brand-600 size-4"
                />
                {t("imp.upload.publish")}
              </label>
              <Button type="submit" loading={busy} disabled={applicable === 0}>
                <CheckCircle2 className="size-4" aria-hidden /> {t("imp.run.apply")} ({applicable})
              </Button>
            </Form>
            <Form method="post" onSubmit={(e) => !confirm(t("imp.run.cancelConfirm")) && e.preventDefault()}>
              <input type="hidden" name="intent" value="cancel" />
              <Button type="submit" variant="ghost" disabled={busy}>
                <X className="size-4" aria-hidden /> {t("imp.run.cancel")}
              </Button>
            </Form>
          </div>
        </Card>
      )}
      {active && (
        <Alert>
          <span className="inline-flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" aria-hidden /> {t("imp.run.applying")}
          </span>
        </Alert>
      )}
      {run.status === "done" && (
        <Alert tone="success">
          {t("imp.run.done")}{" "}
          {!run.options.publish && (run.stats.result?.created ?? 0) > 0 && t("imp.run.doneHidden")}
        </Alert>
      )}
      {run.status === "failed" && <Alert tone="danger">{t("imp.run.failed", { error: run.error })}</Alert>}

      <nav className="flex flex-wrap gap-2" aria-label={t("catalog.filters")}>
        {FILTERS.map((f) => (
          <Link
            key={f}
            to={filterHref(f)}
            className={`rounded-full border px-3 py-1 text-sm ${f === filter ? "border-brand-500 bg-brand-50 text-brand-700 font-medium" : "border-line hover:border-brand-500 bg-white"}`}
          >
            {t(`imp.filter.${f}` as TKey)}
          </Link>
        ))}
      </nav>

      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th>{t("imp.col.row")}</Th>
              <Th>{t("imp.col.action")}</Th>
              <Th>{t("wh.col.sku")}</Th>
              <Th>{t("wh.col.product")}</Th>
              <Th align="right">{t("imp.col.price")}</Th>
              <Th align="right">{t("imp.col.qty")}</Th>
              <Th>{t("imp.col.messages")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.results.length === 0 && (
              <tr>
                <Td colSpan={7} className="text-muted py-8 text-center">
                  {t("imp.rows.empty")}
                </Td>
              </tr>
            )}
            {rows.results.map((row) => (
              <RowLine key={row.row} row={row} />
            ))}
          </tbody>
        </Table>
      </TableWrap>
      <Pagination page={page} pages={pages} />
    </div>
  );
}
