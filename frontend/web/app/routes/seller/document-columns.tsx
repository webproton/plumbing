import { Check, RotateCcw } from "lucide-react";
import { useState } from "react";
import { data, Form, useNavigation } from "react-router";

import { Alert, Button, PageTitle } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError, LONG_TIMEOUT } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";
import type { ColumnMap, ColumnRole, InvoiceDoc, InvoiceTable } from "~/lib/types";

import type { Route } from "./+types/document-columns";

export const meta: Route.MetaFunction = ({ params, matches }) => [
  { title: tFromMatches(matches)("wh.cols.title", { id: params.id ?? "" }) },
];

const ROLES: ColumnRole[] = ["name", "qty", "price", "total", "sku", "barcode", "unit"];
const REQUIRED: ColumnRole[] = ["name", "qty", "price"];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const base = `/warehouse/inventory-documents/${params.id}`;
  try {
    const [doc, table] = await Promise.all([
      api.get<InvoiceDoc>(`${base}/`),
      api.get<InvoiceTable>(`${base}/table/`, { timeoutMs: LONG_TIMEOUT }),
    ]);
    return { doc, table };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data("Not Found", { status: 404 });
    throw e;
  }
}

export async function action({ request, params, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const url = `/warehouse/inventory-documents/${params.id}/columns/`;
  try {
    if (form.get("intent") === "reset") {
      await api.post(url, { reset: true }, { timeoutMs: LONG_TIMEOUT });
    } else {
      const headerRow = String(form.get("header_row") ?? "");
      await api.post(
        url,
        {
          header_row: headerRow === "" ? null : Number(headerRow),
          columns: JSON.parse(String(form.get("columns") ?? "{}")) as ColumnMap["columns"],
          remember: form.get("remember") === "1",
        },
        { timeoutMs: LONG_TIMEOUT },
      );
    }
    return localRedirect(request, `/seller/documents/${params.id}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ error: Object.values(e.fieldErrors)[0] ?? t("error.generic") }, { status: 400 });
  }
}

/** колонка → роль из раскладки {роль: колонка} */
function rolesByColumn(map: ColumnMap | null): Record<number, ColumnRole> {
  const out: Record<number, ColumnRole> = {};
  for (const [role, col] of Object.entries(map?.columns ?? {})) {
    if (col !== undefined) out[col] = role as ColumnRole;
  }
  return out;
}

export default function DocumentColumns({ loaderData, actionData }: Route.ComponentProps) {
  const { doc, table } = loaderData;
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const initial = doc.column_map ?? table.suggested;
  const [roles, setRoles] = useState<Record<number, ColumnRole>>(() => rolesByColumn(initial));
  const [headerRow, setHeaderRow] = useState<number | null>(initial?.header_row ?? null);

  const assign = (col: number, role: ColumnRole | "") =>
    setRoles((prev) => {
      const next: Record<number, ColumnRole> = {};
      for (const [c, r] of Object.entries(prev)) if (r !== role && Number(c) !== col) next[Number(c)] = r;
      if (role) next[col] = role;
      return next;
    });

  const columns = Object.fromEntries(Object.entries(roles).map(([col, role]) => [role, Number(col)]));
  const complete = REQUIRED.every((r) => r in columns);

  return (
    <div className="space-y-5">
      <Link to={`/seller/documents/${doc.id}`} className="text-brand-600 text-sm hover:underline">
        ← {t("wh.doc.title", { id: doc.id })}
      </Link>
      <PageTitle subtitle={t("wh.cols.text")}>{t("wh.cols.title", { id: doc.id })}</PageTitle>

      {table.needs_ai ? (
        <Alert>{t("wh.parse.needsAi")}</Alert>
      ) : (
        <>
          <div className="border-line overflow-x-auto rounded-2xl border bg-white">
            <table className="w-full text-sm">
              <thead className="bg-surface sticky top-0">
                <tr>
                  <th className="border-line text-muted border-b px-2 py-2 text-left text-xs font-semibold">
                    {t("wh.cols.header")}
                  </th>
                  {table.columns.map((col, i) => (
                    <th key={col} className="border-line border-b px-1.5 py-2">
                      <select
                        value={roles[col] ?? ""}
                        onChange={(e) => assign(col, e.target.value as ColumnRole | "")}
                        aria-label={`${i + 1}`}
                        className={`w-full min-w-24 rounded-lg border px-1.5 py-1 text-xs ${roles[col] ? "border-brand-500 bg-brand-50 text-brand-700 font-semibold" : "border-line bg-white"}`}
                      >
                        <option value="">{t("wh.cols.role.none")}</option>
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {t(`wh.cols.role.${r}` as const)}
                          </option>
                        ))}
                      </select>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.map((row) => (
                  <tr
                    key={row.index}
                    onClick={() => setHeaderRow(headerRow === row.index ? null : row.index)}
                    className={`cursor-pointer ${row.index === headerRow ? "bg-brand-50 font-semibold" : headerRow !== null && row.index > headerRow ? "" : "text-muted"} hover:bg-surface`}
                  >
                    <td className="border-line border-b px-2 py-1 text-center">
                      <input
                        type="radio"
                        name="header_pick"
                        checked={row.index === headerRow}
                        onChange={() => setHeaderRow(row.index)}
                        aria-label={`${t("wh.cols.header")} ${row.index + 1}`}
                        className="accent-brand-600"
                      />
                    </td>
                    {row.cells.map((cell, i) => (
                      <td
                        key={table.columns[i]}
                        className={`border-line max-w-64 truncate border-b px-2 py-1 ${roles[table.columns[i]] ? "bg-brand-50/40" : ""}`}
                        title={cell}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-muted text-xs">
            {t("wh.cols.shown", { shown: table.rows.length, total: table.total_rows })}
          </p>

          <Form method="post" className="space-y-3">
            <input type="hidden" name="columns" value={JSON.stringify(columns)} />
            <input type="hidden" name="header_row" value={headerRow ?? ""} />
            {doc.supplier ? (
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" name="remember" value="1" className="accent-brand-600 mt-0.5 size-4" />
                {t("wh.cols.remember", { name: doc.supplier_name ?? "" })}
              </label>
            ) : (
              <p className="text-muted text-sm">{t("wh.cols.rememberNoSupplier")}</p>
            )}
            {!complete && <p className="text-danger text-sm">{t("wh.cols.required")}</p>}
            {actionData?.error && <Alert tone="danger">{actionData.error}</Alert>}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={busy} disabled={!complete}>
                <Check className="size-4" aria-hidden /> {t("wh.cols.apply")}
              </Button>
              {headerRow !== null && (
                <Button type="button" variant="ghost" onClick={() => setHeaderRow(null)}>
                  {t("wh.cols.noHeader")}
                </Button>
              )}
            </div>
          </Form>
          {doc.column_map && (
            <Form method="post">
              <input type="hidden" name="intent" value="reset" />
              <Button type="submit" variant="ghost" size="sm" disabled={busy}>
                <RotateCcw className="size-4" aria-hidden /> {t("wh.cols.reset")}
              </Button>
            </Form>
          )}
        </>
      )}
    </div>
  );
}
