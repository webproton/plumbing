import { FileDown, FileSpreadsheet, FileUp } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { Pagination } from "~/components/Pagination";
import { RunStatusBadge, usePolling, ACTIVE_RUN } from "~/components/seller/imports";
import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import {
  Alert,
  Button,
  buttonClass,
  Card,
  EmptyState,
  Field,
  Input,
  PageTitle,
  Select,
} from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useLang, useLocalPath, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError, LONG_TIMEOUT } from "~/lib/api.server";
import { formatDateTime } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { ImportRun, Paginated } from "~/lib/types";

import type { Route } from "./+types/import";
import { useSellerMe } from "./layout";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("imp.nav") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const page = pageOf(request);
  const runs = await paged(
    api.get<Paginated<ImportRun>>("/imports/runs/", { query: { kind: "template", page } }),
  );
  return { ...runs, page, pages: pagesOf(runs) };
}

const MAX_BYTES = 20 * 1024 * 1024;

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0)
    return data({ error: t("imp.upload.chooseFile") }, { status: 400 });
  if (file.size > MAX_BYTES) return data({ error: t("imp.upload.tooBig") }, { status: 400 });

  const body = new FormData();
  body.set("file", file);
  const warehouse = String(form.get("warehouse") ?? "");
  if (warehouse) body.set("warehouse", warehouse);
  body.set("publish", form.get("publish") === "1" ? "true" : "false");
  try {
    const run = await api.post<ImportRun>("/imports/runs/", body, { timeoutMs: LONG_TIMEOUT });
    return localRedirect(request, `/seller/import/${run.id}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ error: Object.values(e.fieldErrors)[0] ?? t("error.generic") }, { status: 400 });
  }
}

export default function ImportPage({ loaderData, actionData }: Route.ComponentProps) {
  const { results, page, pages } = loaderData;
  const t = useT();
  const lang = useLang();
  const local = useLocalPath();
  const me = useSellerMe();
  const uploading = useNavigation().state === "submitting";
  const defaultWarehouse = me.warehouses.find((w) => w.is_default)?.id ?? "";
  usePolling(results.some((r) => ACTIVE_RUN.includes(r.status)));

  const templateHref = (type: "xlsx" | "csv", products = false) =>
    local(`/seller/import/template?type=${type}${products ? "&products=1" : ""}`);

  return (
    <div className="space-y-6">
      <PageTitle subtitle={t("imp.subtitle")}>{t("imp.nav")}</PageTitle>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card className="space-y-4 p-5">
          <div>
            <h2 className="font-semibold">{t("imp.template.title")}</h2>
            <p className="text-muted mt-1 text-sm">{t("imp.template.text")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a href={templateHref("xlsx")} className={buttonClass("secondary", "sm")} download>
              <FileSpreadsheet className="size-4" aria-hidden /> {t("imp.template.xlsx")}
            </a>
            <a href={templateHref("csv")} className={buttonClass("secondary", "sm")} download>
              <FileDown className="size-4" aria-hidden /> {t("imp.template.csv")}
            </a>
            <a href={templateHref("xlsx", true)} className={buttonClass("ghost", "sm")} download>
              <FileDown className="size-4" aria-hidden /> {t("imp.template.export")}
            </a>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="mb-3 font-semibold">{t("imp.upload.title")}</h2>
          <Form method="post" encType="multipart/form-data" className="space-y-4">
            <Field label={t("imp.upload.file")} hint={t("imp.upload.fileHint")}>
              {(p) => (
                <Input {...p} name="file" type="file" accept=".xlsx,.xls,.csv" required className="py-2" />
              )}
            </Field>
            <div className="grid items-end gap-4 sm:grid-cols-2">
              <Field label={t("imp.upload.warehouse")}>
                {(p) => (
                  <Select {...p} name="warehouse" defaultValue={defaultWarehouse}>
                    <option value="">{t("imp.upload.noWarehouse")}</option>
                    {me.warehouses.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <label className="flex items-start gap-2 pb-2.5 text-sm">
                <input type="checkbox" name="publish" value="1" className="accent-brand-600 mt-0.5 size-4" />
                <span>
                  {t("imp.upload.publish")}
                  <span className="text-muted block">{t("imp.upload.publishHint")}</span>
                </span>
              </label>
            </div>
            {actionData?.error && <Alert tone="danger">{actionData.error}</Alert>}
            <Button type="submit" loading={uploading}>
              <FileUp className="size-4" aria-hidden /> {t("imp.upload.submit")}
            </Button>
          </Form>
        </Card>
      </div>

      <h2 className="text-lg font-semibold">{t("imp.history")}</h2>
      {results.length === 0 ? (
        <EmptyState icon={FileSpreadsheet} title={t("imp.empty")} />
      ) : (
        <>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>№</Th>
                  <Th>{t("imp.col.file")}</Th>
                  <Th>{t("wh.col.date")}</Th>
                  <Th>{t("wh.doc.status")}</Th>
                  <Th>{t("imp.col.result")}</Th>
                </tr>
              </thead>
              <tbody>
                {results.map((run) => {
                  const r = run.stats.result;
                  return (
                    <tr key={run.id} className="hover:bg-surface">
                      <Td>
                        <Link
                          to={`/seller/import/${run.id}`}
                          className="text-brand-700 font-semibold hover:underline"
                        >
                          #{run.id}
                        </Link>
                      </Td>
                      <Td className="max-w-64 truncate">{run.file_name}</Td>
                      <Td className="text-muted whitespace-nowrap">{formatDateTime(run.created_at, lang)}</Td>
                      <Td>
                        <RunStatusBadge status={run.status} />
                      </Td>
                      <Td className="text-muted">
                        {r
                          ? t("imp.result", r)
                          : t("imp.summary", {
                              create: run.stats.create ?? 0,
                              update: run.stats.update ?? 0,
                              errors: run.stats.errors ?? 0,
                            })}
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </TableWrap>
          <Pagination page={page} pages={pages} />
        </>
      )}
    </div>
  );
}
