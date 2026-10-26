import { FileUp, FileText } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { Pagination } from "~/components/Pagination";
import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, PageTitle, Select } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError } from "~/lib/api.server";
import { formatDate } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { InvoiceDoc, Paginated, Supplier } from "~/lib/types";

import type { Route } from "./+types/documents";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("wh.nav.documents") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const page = pageOf(request);
  const [docs, suppliers] = await Promise.all([
    paged(api.get<Paginated<InvoiceDoc>>("/warehouse/inventory-documents/", { query: { page } })),
    api.get<Supplier[]>("/warehouse/suppliers/"),
  ]);
  return { ...docs, page, pages: pagesOf(docs), suppliers: suppliers.filter((s) => s.is_active) };
}

const MAX_BYTES = 10 * 1024 * 1024;

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return data({ error: t("wh.doc.chooseFile"), duplicateId: null as number | null }, { status: 400 });
  }
  if (file.size > MAX_BYTES) return data({ error: t("wh.doc.tooBig"), duplicateId: null }, { status: 400 });

  const body = new FormData();
  body.set("file", file);
  body.set("document_type", "incoming");
  const supplier = String(form.get("supplier") ?? "");
  if (supplier) body.set("supplier", supplier);
  try {
    const doc = await api.post<InvoiceDoc>("/warehouse/inventory-documents/", body);
    return localRedirect(request, `/seller/documents/${doc.id}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const b = e.body as { document_id?: number } | null;
    return data(
      { error: Object.values(e.fieldErrors)[0] ?? t("error.generic"), duplicateId: b?.document_id ?? null },
      { status: 400 },
    );
  }
}

export function DocStatus({ doc }: { doc: Pick<InvoiceDoc, "processed" | "summary" | "extracted_data"> }) {
  const t = useT();
  if (doc.processed) return <Badge tone="success">{t("wh.doc.status.processed")}</Badge>;
  if (doc.extracted_data?.reversals?.length) return <Badge tone="muted">{t("wh.doc.status.reversed")}</Badge>;
  if (doc.extracted_data?.error) return <Badge tone="danger">{t("wh.doc.status.error")}</Badge>;
  if ((doc.summary?.needs_review ?? 0) > 0) return <Badge tone="danger">{t("wh.doc.status.review", { n: doc.summary?.needs_review ?? 0 })}</Badge>;
  return <Badge>{t("wh.doc.status.ready")}</Badge>;
}

export default function Documents({ loaderData, actionData }: Route.ComponentProps) {
  const { results, page, pages, suppliers } = loaderData;
  const t = useT();
  const lang = useLang();
  const uploading = useNavigation().state === "submitting";

  return (
    <div className="space-y-6">
      <PageTitle subtitle={t("wh.doc.subtitle")} help="documents">{t("wh.nav.documents")}</PageTitle>

      <Card className="p-5">
        <Form method="post" encType="multipart/form-data" className="grid items-end gap-4 sm:grid-cols-[1fr_16rem_auto]">
          <Field label={t("wh.doc.file")} hint={t("wh.doc.fileHint")}>
            {(p) => <Input {...p} name="file" type="file" accept=".xlsx,.xls,.xml,.yml,.pdf,.jpg,.jpeg,.png,.webp" required className="py-2" />}
          </Field>
          <Field label={t("wh.col.supplier")} hint={t("wh.doc.supplierHint")}>
            {(p) => (
              <Select {...p} name="supplier" defaultValue="">
                <option value="">{t("wh.doc.autoSupplier")}</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Button type="submit" loading={uploading}>
            <FileUp className="size-4" aria-hidden /> {t("wh.doc.upload")}
          </Button>
        </Form>
        {actionData?.error && (
          <div className="mt-4">
            <Alert tone="danger">
              {actionData.error}{" "}
              {actionData.duplicateId && (
                <Link to={`/seller/documents/${actionData.duplicateId}`} className="font-semibold underline">
                  {t("wh.doc.openExisting")}
                </Link>
              )}
            </Alert>
          </div>
        )}
      </Card>

      {results.length === 0 ? (
        <EmptyState icon={FileText} title={t("wh.doc.empty")}>
          {t("wh.doc.emptyText")}
        </EmptyState>
      ) : (
        <>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>№</Th>
                  <Th>{t("wh.doc.number")}</Th>
                  <Th>{t("wh.col.supplier")}</Th>
                  <Th>{t("wh.col.date")}</Th>
                  <Th>{t("wh.doc.status")}</Th>
                  <Th align="right">{t("wh.doc.movements")}</Th>
                </tr>
              </thead>
              <tbody>
                {results.map((d) => (
                  <tr key={d.id} className="hover:bg-surface">
                    <Td>
                      <Link to={`/seller/documents/${d.id}`} className="font-semibold text-brand-700 hover:underline">
                        #{d.id}
                      </Link>
                    </Td>
                    <Td>{d.document_number ?? "—"}</Td>
                    <Td>{d.supplier_name ?? "—"}</Td>
                    <Td className="whitespace-nowrap text-muted">{formatDate(d.uploaded_at, lang)}</Td>
                    <Td>
                      <DocStatus doc={d} />
                    </Td>
                    <Td align="right">{d.movements_count}</Td>
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
