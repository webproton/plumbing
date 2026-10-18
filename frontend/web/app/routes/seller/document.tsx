import { Check, ChevronDown, Download, FileDown, PackagePlus, RefreshCw } from "lucide-react";
import { useState } from "react";
import { data, Form, useFetcher, useNavigation } from "react-router";

import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { VariantPicker } from "~/components/seller/VariantPicker";
import { Alert, Badge, Button, Card, Field, PageTitle, Select } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TFunction } from "~/i18n";
import { Link, useLang, useLocalPath, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { formatDate, formatQty } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";
import type { InvoiceDoc, InvoiceLine, LineStatus, ProcessingReport, Supplier } from "~/lib/types";

import type { Route } from "./+types/document";
import { DocStatus } from "./documents";
import { useSellerMe } from "./layout";

export const meta: Route.MetaFunction = ({ params, matches }) => [
  { title: tFromMatches(matches)("wh.doc.title", { id: params.id ?? "" }) },
];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  try {
    const [doc, suppliers] = await Promise.all([
      api.get<InvoiceDoc & { variants: Record<string, { name: string; sku: string | null }> }>(
        `/warehouse/inventory-documents/${params.id}/`,
      ),
      api.get<Supplier[]>("/warehouse/suppliers/"),
    ]);
    return { doc, suppliers: suppliers.filter((s) => s.is_active) };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data("Not Found", { status: 404 });
    throw e;
  }
}

export async function action({ request, params, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const intent = String(form.get("intent"));
  const base = `/warehouse/inventory-documents/${params.id}`;
  try {
    if (intent === "set_line") {
      const create = form.get("create_new") === "1";
      await api.post(`${base}/lines/${Number(form.get("position"))}/`, create ? { create_new: true } : { variant: Number(form.get("variant")) });
      return { ok: true as const, intent };
    }
    if (intent === "reparse") {
      await api.post(`${base}/parse/`);
      return { ok: true as const, intent };
    }
    if (intent === "set_supplier") {
      await api.patch(`${base}/`, { supplier: Number(form.get("supplier")) || null });
      await api.post(`${base}/parse/`);
      return { ok: true as const, intent };
    }
    if (intent === "process") {
      const report = await api.post<ProcessingReport>(`${base}/process/`, {
        warehouse: Number(form.get("warehouse")) || undefined,
        accept_suggestions: form.get("accept_suggestions") === "1",
        allow_duplicate_number: form.get("allow_duplicate_number") === "1",
      });
      return { ok: true as const, intent, report };
    }
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, intent, code: e.code ?? null, error: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
  return data({ ok: false as const, intent, code: null, error: t("error.generic") }, { status: 400 });
}

const STATUS_TONE: Record<LineStatus, "success" | "info" | "danger" | "muted"> = {
  matched: "success",
  new: "info",
  needs_review: "danger",
  invalid: "muted",
};

export default function Document({ loaderData, actionData }: Route.ComponentProps) {
  const { doc, suppliers } = loaderData;
  const me = useSellerMe();
  const t = useT();
  const lang = useLang();
  const local = useLocalPath();
  const busy = useNavigation().state === "submitting";
  const [onlyProblems, setOnlyProblems] = useState(false);

  const lines = doc.extracted_data?.lines ?? [];
  const summary = doc.summary;
  const needsReview = summary?.needs_review ?? 0;
  const shown = onlyProblems ? lines.filter((l) => l.status === "needs_review" || l.status === "invalid") : lines;
  const report = doc.extracted_data?.processing_report ?? (actionData?.ok && "report" in actionData ? actionData.report : null);
  const defaultWh = me.warehouses.find((w) => w.is_default)?.id ?? me.warehouses[0]?.id;
  const failed = actionData && !actionData.ok ? actionData : null;

  return (
    <div className="space-y-5">
      <Link to="/seller/documents" className="text-sm text-brand-600 hover:underline">
        ← {t("wh.nav.documents")}
      </Link>
      <PageTitle
        subtitle={`${formatDate(doc.uploaded_at, lang)}${doc.document_number ? ` · №${doc.document_number}` : ""}${doc.supplier_name ? ` · ${doc.supplier_name}` : ""}`}
      >
        {t("wh.doc.title", { id: doc.id })}
      </PageTitle>

      <div className="flex flex-wrap items-center gap-3">
        <DocStatus doc={doc} />
        {(["matched", "needs_review", "new", "invalid"] as const).map(
          (s) =>
            (summary?.[s] ?? 0) > 0 && (
              <Badge key={s} tone={STATUS_TONE[s]}>
                {t(`wh.line.${s}` as const)}: {summary?.[s]}
              </Badge>
            ),
        )}
        <a
          href={local(`/seller/documents/${doc.id}/file`)}
          className="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline"
          download
        >
          <FileDown className="size-4" aria-hidden /> {t("wh.doc.downloadOriginal")}
        </a>
      </div>

      {doc.extracted_data?.error && <Alert tone="danger">{t("wh.doc.parseError", { error: doc.extracted_data.error })}</Alert>}
      {!doc.processed && !doc.supplier && (
        <Alert tone="info">
          <Form method="post" className="flex flex-wrap items-center gap-3">
            <input type="hidden" name="intent" value="set_supplier" />
            <span>{t("wh.doc.noSupplier")}</span>
            <Select name="supplier" className="max-w-56" defaultValue="" aria-label={t("wh.col.supplier")}>
              <option value="">—</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
            <Button type="submit" size="sm" variant="secondary" loading={busy}>
              {t("wh.doc.setSupplier")}
            </Button>
          </Form>
        </Alert>
      )}
      {failed && failed.intent !== "process" && <Alert tone="danger">{failed.error}</Alert>}

      {lines.length > 0 && (
        <>
          <div className="flex items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} className="size-4 accent-brand-600" />
              {t("wh.doc.onlyProblems")}
            </label>
            {!doc.processed && (
              <Form method="post">
                <input type="hidden" name="intent" value="reparse" />
                <Button type="submit" variant="ghost" size="sm" loading={busy}>
                  <RefreshCw className="size-4" aria-hidden /> {t("wh.doc.reparse")}
                </Button>
              </Form>
            )}
          </div>
          <TableWrap>
            <Table className="min-w-[56rem]">
              <thead>
                <tr>
                  <Th>#</Th>
                  <Th>{t("wh.doc.fromInvoice")}</Th>
                  <Th align="right">{t("wh.col.qty")}</Th>
                  <Th align="right">{t("wh.col.price")}</Th>
                  <Th>{t("wh.doc.matchedTo")}</Th>
                  {!doc.processed && <Th>{t("wh.doc.action")}</Th>}
                </tr>
              </thead>
              <tbody>
                {shown.map((line) => (
                  <LineRow key={line.position} line={line} variants={doc.variants} editable={!doc.processed} t={t} />
                ))}
              </tbody>
            </Table>
          </TableWrap>
        </>
      )}

      {report && (
        <Alert tone="success">
          {t("wh.doc.report", { received: report.received, created: report.created })}{" "}
          <Link to={`/seller/movements?document=${doc.id}`} className="font-semibold underline">
            {t("wh.nav.movements")}
          </Link>
          {report.skipped.length > 0 && (
            <ul className="mt-2 list-disc pl-5">
              {report.skipped.map((s) => (
                <li key={s.row}>
                  {t("wh.doc.skippedRow", { row: s.row })}: {s.reason}
                </li>
              ))}
            </ul>
          )}
        </Alert>
      )}

      {!doc.processed && lines.length > 0 && (
        <Card className="sticky bottom-3 space-y-3 p-4 shadow-lg">
          {failed?.intent === "process" && (
            <Alert tone="danger">
              {failed.error}
              {failed.code === "duplicate_document" && ` ${t("wh.doc.duplicateHint")}`}
            </Alert>
          )}
          <Form method="post" className="flex flex-wrap items-end gap-4">
            <input type="hidden" name="intent" value="process" />
            <Field label={t("wh.doc.toWarehouse")}>
              {(p) => (
                <Select {...p} name="warehouse" defaultValue={defaultWh} className="min-w-48">
                  {me.warehouses.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <div className="space-y-1.5 text-sm">
              {needsReview > 0 && (
                <label className="flex items-center gap-2">
                  <input type="checkbox" name="accept_suggestions" value="1" className="size-4 accent-brand-600" />
                  {t("wh.doc.acceptSuggestions", { n: needsReview })}
                </label>
              )}
              {failed?.code === "duplicate_document" && (
                <label className="flex items-center gap-2">
                  <input type="checkbox" name="allow_duplicate_number" value="1" className="size-4 accent-brand-600" />
                  {t("wh.doc.allowDuplicate")}
                </label>
              )}
            </div>
            <Button type="submit" size="lg" loading={busy} disabled={Boolean(doc.extracted_data?.error)}>
              <Download className="size-4" aria-hidden /> {t("wh.doc.process")}
            </Button>
          </Form>
        </Card>
      )}
    </div>
  );
}

function LineRow({
  line,
  variants,
  editable,
  t,
}: {
  line: InvoiceLine;
  variants: Record<string, { name: string; sku: string | null }>;
  editable: boolean;
  t: TFunction;
}) {
  const fetcher = useFetcher<{ ok: boolean; error?: string }>();
  const [picking, setPicking] = useState(false);
  const submit = (fields: Record<string, string>) =>
    fetcher.submit({ intent: "set_line", position: String(line.position), ...fields }, { method: "post" });
  const matchName = line.variant_id ? (variants[String(line.variant_id)]?.name ?? `#${line.variant_id}`) : null;
  const busy = fetcher.state !== "idle";

  return (
    <tr className={line.status === "needs_review" ? "bg-warning/10" : line.status === "invalid" ? "bg-line/40" : undefined}>
      <Td className="text-muted">{line.position}</Td>
      <Td>
        <p className="font-medium">{line.name || "—"}</p>
        <p className="text-xs text-muted">{[line.sku, line.barcode].filter(Boolean).join(" · ")}</p>
      </Td>
      <Td align="right">{line.qty ? `${formatQty(line.qty)} ${line.unit}` : "—"}</Td>
      <Td align="right">{line.price ?? "—"}</Td>
      <Td>
        <Badge tone={STATUS_TONE[line.status]}>{t(`wh.line.${line.status}` as const)}</Badge>
        {line.status === "invalid" ? (
          <p className="mt-1 text-xs text-muted">{line.error}</p>
        ) : line.status === "new" ? (
          <p className="mt-1 text-xs text-muted">{t("wh.line.newHint")}</p>
        ) : matchName ? (
          <p className="mt-1 text-sm">
            {matchName}
            {line.method && <span className="text-xs text-muted"> · {t(`wh.method.${line.method}` as const)}</span>}
          </p>
        ) : null}
        {fetcher.data?.error && <p className="mt-1 text-xs text-danger">{fetcher.data.error}</p>}
      </Td>
      {editable && (
        <Td className="min-w-64">
          {line.status === "invalid" ? null : picking ? (
            <div className="space-y-2">
              <VariantPicker onSelect={(v) => v && (submit({ variant: String(v.id) }), setPicking(false))} />
              <button type="button" className="text-xs text-muted hover:text-ink" onClick={() => setPicking(false)}>
                {t("common.back")}
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {line.status === "needs_review" &&
                line.candidates.slice(0, 2).map((c) => (
                  <Button key={c.variant_id} type="button" size="sm" loading={busy} onClick={() => submit({ variant: String(c.variant_id) })}>
                    <Check className="size-3.5" aria-hidden />
                    {variants[String(c.variant_id)]?.name.slice(0, 22) ?? `#${c.variant_id}`} · {c.score}%
                  </Button>
                ))}
              <Button type="button" size="sm" variant="secondary" onClick={() => setPicking(true)}>
                <ChevronDown className="size-3.5" aria-hidden /> {t("wh.line.pick")}
              </Button>
              {line.status !== "new" && (
                <Button type="button" size="sm" variant="ghost" loading={busy} onClick={() => submit({ create_new: "1" })}>
                  <PackagePlus className="size-3.5" aria-hidden /> {t("wh.line.createNew")}
                </Button>
              )}
            </div>
          )}
        </Td>
      )}
    </tr>
  );
}
