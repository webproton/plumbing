import { Plus, RefreshCw, Rss } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { Pagination } from "~/components/Pagination";
import { intervalLabel, SourceStatusBadge, usePolling } from "~/components/seller/imports";
import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, Button, ButtonLink, EmptyState, PageTitle } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TKey } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { formatDateTime } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { ImportSource, Paginated } from "~/lib/types";

import type { Route } from "./+types/sources";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("src.nav") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const page = pageOf(request);
  const sources = await paged(api.get<Paginated<ImportSource>>("/imports/sources/", { query: { page } }));
  return { ...sources, page, pages: pagesOf(sources) };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  try {
    await api.post(`/imports/sources/${Number(form.get("id"))}/sync/`);
    return { ok: true as const, error: null };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, error: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
}

export default function Sources({ loaderData, actionData }: Route.ComponentProps) {
  const { results, page, pages } = loaderData;
  const t = useT();
  const lang = useLang();
  const nav = useNavigation();
  const syncing = nav.state === "submitting" ? Number(nav.formData?.get("id")) : null;
  usePolling(results.some((s) => s.last_status === "running"));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageTitle subtitle={t("src.subtitle")} help="sources">{t("src.nav")}</PageTitle>
        <ButtonLink to="/seller/sources/new">
          <Plus className="size-4" aria-hidden /> {t("src.add")}
        </ButtonLink>
      </div>
      {actionData?.ok && <Alert tone="success">{t("src.syncQueued")}</Alert>}
      {actionData?.error && <Alert tone="danger">{actionData.error}</Alert>}

      {results.length === 0 ? (
        <EmptyState icon={Rss} title={t("src.empty")}>
          {t("src.emptyText")}
        </EmptyState>
      ) : (
        <>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>{t("src.form.name")}</Th>
                  <Th align="right">{t("src.col.items")}</Th>
                  <Th align="right">{t("src.col.new")}</Th>
                  <Th align="right">{t("src.col.linked")}</Th>
                  <Th>{t("src.col.sync")}</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {results.map((s) => (
                  <tr key={s.id} className="hover:bg-surface align-top">
                    <Td>
                      <Link
                        to={`/seller/sources/${s.id}`}
                        className="text-brand-700 font-semibold hover:underline"
                      >
                        {s.name}
                      </Link>
                      <p className="text-muted text-xs">
                        {t(`src.kind.${s.kind}` as TKey)}
                        {s.supplier_name && ` · ${s.supplier_name}`}
                      </p>
                    </Td>
                    <Td align="right">{s.counts?.total ?? 0}</Td>
                    <Td align="right">{s.counts?.new ?? 0}</Td>
                    <Td align="right">{s.counts?.linked ?? 0}</Td>
                    <Td className="text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <SourceStatusBadge source={s} />
                        <span className="text-muted">
                          {s.last_sync_at ? formatDateTime(s.last_sync_at, lang) : ""}
                        </span>
                      </div>
                      <p className="text-muted text-xs">{t(intervalLabel(s.sync_interval_minutes))}</p>
                      {s.last_status === "error" && (
                        <p className="text-danger mt-1 max-w-72 text-xs">{s.last_error}</p>
                      )}
                    </Td>
                    <Td className="text-right">
                      <Form method="post">
                        <input type="hidden" name="id" value={s.id} />
                        <Button
                          type="submit"
                          size="sm"
                          variant="secondary"
                          loading={syncing === s.id}
                          disabled={s.last_status === "running"}
                        >
                          <RefreshCw className="size-3.5" aria-hidden /> {t("src.sync")}
                        </Button>
                      </Form>
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
