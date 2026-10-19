import {
  ExternalLink,
  EyeOff,
  Link2,
  PackagePlus,
  RefreshCw,
  RotateCcw,
  Settings,
  Undo2,
} from "lucide-react";
import { useState } from "react";
import { data, Form, useFetcher, useNavigation, useSearchParams } from "react-router";

import { Pagination } from "~/components/Pagination";
import { RunStatusBadge, SourceStatusBadge, usePolling } from "~/components/seller/imports";
import { StatCard, Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { VariantPicker } from "~/components/seller/VariantPicker";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  Input,
  PageTitle,
  Select,
} from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TKey } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { ApiError, LONG_TIMEOUT } from "~/lib/api.server";
import { formatDateTime, formatPrice, formatQty } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type {
  Category,
  ImportRun,
  ImportSource,
  Paginated,
  SupplierCategory,
  SupplierItemRow,
} from "~/lib/types";

import type { Route } from "./+types/source";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("src.nav") }];

const TABS = ["new", "linked", "ignored", "all"] as const;
type Tab = (typeof TABS)[number];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const tab: Tab = TABS.find((s) => s === q.get("status")) ?? "new";
  const page = pageOf(request);
  const base = `/imports/sources/${params.id}`;
  try {
    const [source, items, supplierCategories, runs, categories] = await Promise.all([
      api.get<ImportSource>(`${base}/`),
      paged(
        api.get<Paginated<SupplierItemRow>>(`${base}/items/`, {
          query: {
            status: tab === "all" ? undefined : tab,
            q: q.get("q") || undefined,
            category: q.get("category") || undefined,
            missing: q.get("missing") || undefined,
            available: q.get("available") || undefined,
            page,
          },
        }),
      ),
      api.get<SupplierCategory[]>(`${base}/categories/`),
      api.get<ImportRun[]>(`${base}/runs/`),
      api.get<Category[]>("/category/"),
    ]);
    return {
      source,
      items,
      supplierCategories,
      runs: runs.slice(0, 5),
      categories,
      tab,
      page,
      pages: pagesOf(items),
    };
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
  const base = `/imports/sources/${params.id}`;
  const ids = form.getAll("ids").map(Number).filter(Boolean);
  try {
    if (intent === "sync") {
      await api.post(`${base}/sync/`);
      return { ok: true as const, intent, message: t("src.syncQueued") };
    }
    if (intent === "link") {
      await api.post(`${base}/link/`, {
        item: Number(form.get("item")),
        variant: Number(form.get("variant")),
      });
      return { ok: true as const, intent, message: t("src.linkedOk") };
    }
    if (intent === "publish") {
      const r = await api.post<{ created: number; linked: number; skipped: number; photos_queued: number }>(
        `${base}/publish/`,
        {
          ids,
          category: Number(form.get("category")) || null,
          visible: form.get("visible") === "1",
        },
        { timeoutMs: LONG_TIMEOUT },
      );
      const photos = r.photos_queued > 0 ? ` ${t("src.photosQueued")}` : "";
      return { ok: true as const, intent, message: t("src.published", r) + photos };
    }
    if (intent === "ignored" || intent === "new") {
      const r = await api.post<{ changed: number }>(`${base}/items-status/`, { ids, status: intent });
      return { ok: true as const, intent, message: t("src.statusChanged", { n: r.changed }) };
    }
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, intent, message: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
  return data({ ok: false as const, intent, message: t("error.generic") }, { status: 400 });
}

function LinkRow({ item, onDone }: { item: SupplierItemRow; onDone: () => void }) {
  const t = useT();
  const fetcher = useFetcher<typeof action>();
  const error = fetcher.data && !fetcher.data.ok ? fetcher.data.message : undefined;
  return (
    <tr>
      <Td colSpan={6} className="bg-brand-50/50">
        <fetcher.Form method="post" className="flex flex-wrap items-start gap-3">
          <input type="hidden" name="intent" value="link" />
          <input type="hidden" name="item" value={item.id} />
          <div className="min-w-72 flex-1">
            <p className="mb-2 text-sm font-medium">{t("src.link.title", { name: item.name })}</p>
            <VariantPicker name="variant" error={error} />
          </div>
          <div className="flex gap-2 pt-7">
            <Button type="submit" size="sm" loading={fetcher.state !== "idle"}>
              <Link2 className="size-3.5" aria-hidden /> {t("src.link")}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={onDone}>
              {t("imp.run.cancel")}
            </Button>
          </div>
        </fetcher.Form>
      </Td>
    </tr>
  );
}

function stockLabel(item: SupplierItemRow, t: ReturnType<typeof useT>) {
  if (item.quantity != null) return formatQty(item.quantity);
  if (item.available === true) return t("src.item.inStock");
  if (item.available === false) return t("src.item.outOfStock");
  return "—";
}

function ItemsTable({
  items,
  tab,
  categories,
}: {
  items: SupplierItemRow[];
  tab: Tab;
  categories: Category[];
}) {
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [linking, setLinking] = useState<number | null>(null);
  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const allSelected = items.length > 0 && items.every((i) => selected.has(i.id));
  const selectable = items.filter((i) => i.status !== "linked");

  return (
    <div className="space-y-3">
      {/* массовые действия: чекбоксы в таблице привязаны к этой форме атрибутом form="bulk" */}
      <Form
        id="bulk"
        method="post"
        className="border-line flex flex-wrap items-center gap-3 rounded-2xl border bg-white p-3"
      >
        <span className="text-sm font-medium">{t("src.bulk.selected", { n: selected.size })}</span>
        {tab !== "ignored" && (
          <>
            <Select
              name="category"
              defaultValue=""
              className="w-56 py-1.5 text-sm"
              aria-label={t("src.bulk.publishTo")}
            >
              <option value="">{t("src.bulk.publishTo")}…</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="visible" value="1" className="accent-brand-600 size-4" />
              {t("src.bulk.visible")}
            </label>
            <Button
              type="submit"
              name="intent"
              value="publish"
              size="sm"
              disabled={selected.size === 0}
              loading={busy}
            >
              <PackagePlus className="size-3.5" aria-hidden /> {t("src.bulk.publish")}
            </Button>
            <Button
              type="submit"
              name="intent"
              value="ignored"
              size="sm"
              variant="secondary"
              disabled={selected.size === 0}
            >
              <EyeOff className="size-3.5" aria-hidden /> {t("src.bulk.ignore")}
            </Button>
          </>
        )}
        {tab !== "new" && (
          <Button
            type="submit"
            name="intent"
            value="new"
            size="sm"
            variant="secondary"
            disabled={selected.size === 0}
          >
            <Undo2 className="size-3.5" aria-hidden /> {t("src.bulk.restore")}
          </Button>
        )}
      </Form>

      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th className="w-10">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={() => setSelected(allSelected ? new Set() : new Set(selectable.map((i) => i.id)))}
                  aria-label={t("src.bulk.selectAll")}
                  className="accent-brand-600 size-4"
                />
              </Th>
              <Th>{t("wh.col.product")}</Th>
              <Th align="right">{t("src.col.supplierPrice")}</Th>
              <Th align="right">{t("src.col.ourPrice")}</Th>
              <Th align="right">{t("src.col.stock")}</Th>
              <Th>{t("src.col.ourProduct")}</Th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <ItemRow
                key={item.id}
                item={item}
                checked={selected.has(item.id)}
                onToggle={() => toggle(item.id)}
                linking={linking === item.id}
                onLink={() => setLinking(linking === item.id ? null : item.id)}
              />
            ))}
          </tbody>
        </Table>
      </TableWrap>
    </div>
  );
}

function ItemRow({
  item,
  checked,
  onToggle,
  linking,
  onLink,
}: {
  item: SupplierItemRow;
  checked: boolean;
  onToggle: () => void;
  linking: boolean;
  onLink: () => void;
}) {
  const t = useT();
  const foreign = item.currency && item.currency !== "UAH" ? ` ${item.currency}` : "";
  return (
    <>
      <tr className="hover:bg-surface align-top">
        <Td>
          <input
            type="checkbox"
            form="bulk"
            name="ids"
            value={item.id}
            checked={checked}
            onChange={onToggle}
            aria-label={item.name}
            className="accent-brand-600 size-4"
          />
        </Td>
        <Td className="min-w-64">
          <div className="flex gap-3">
            {item.photo ? (
              <img
                src={item.photo}
                alt=""
                loading="lazy"
                referrerPolicy="no-referrer"
                className="border-line size-12 shrink-0 rounded-lg border object-contain"
              />
            ) : (
              <div className="bg-surface size-12 shrink-0 rounded-lg" />
            )}
            <div className="min-w-0">
              <p className="font-medium">
                {item.name || item.external_id}
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-muted hover:text-brand-700 ml-1 inline-block"
                  >
                    <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                )}
              </p>
              <p className="text-muted text-xs">
                {[item.sku, item.barcode, item.brand, item.category_name].filter(Boolean).join(" · ")}
              </p>
              {item.missing && <Badge tone="danger">{t("src.item.missing")}</Badge>}
            </div>
          </div>
        </Td>
        <Td align="right" className="whitespace-nowrap">
          {item.price ? `${formatPrice(item.price)}${foreign}` : "—"}
          {item.cost && (
            <p className="text-muted text-xs">
              {t("src.item.cost", { price: `${formatPrice(item.cost)}${foreign}` })}
            </p>
          )}
        </Td>
        <Td align="right" className="font-medium whitespace-nowrap">
          {item.our_price ? formatPrice(item.our_price) : "—"}
          {item.variant_price && item.variant_price !== item.our_price && (
            <p className="text-muted text-xs font-normal">{formatPrice(item.variant_price)}</p>
          )}
        </Td>
        <Td align="right">{stockLabel(item, t)}</Td>
        <Td className="min-w-44">
          {item.variant ? (
            <>
              <p className="text-sm">{item.variant_name}</p>
              {item.match_method && (
                <p className="text-muted text-xs">{t(`src.method.${item.match_method}` as TKey)}</p>
              )}
            </>
          ) : item.status === "ignored" ? (
            <Badge tone="muted">{t("src.items.ignored")}</Badge>
          ) : (
            <Button type="button" size="sm" variant="ghost" onClick={onLink}>
              <Link2 className="size-3.5" aria-hidden /> {t("src.link")}
            </Button>
          )}
        </Td>
      </tr>
      {linking && <LinkRow item={item} onDone={onLink} />}
    </>
  );
}

export default function SourcePage({ loaderData, actionData }: Route.ComponentProps) {
  const { source, items, supplierCategories, runs, categories, tab, page, pages } = loaderData;
  const t = useT();
  const lang = useLang();
  const [params] = useSearchParams();
  const nav = useNavigation();
  const running =
    source.last_status === "running" || runs.some((r) => r.status === "pending" || r.status === "running");
  usePolling(running);

  const tabHref = (s: Tab) => {
    const next = new URLSearchParams(params);
    next.delete("page");
    next.set("status", s);
    return `/seller/sources/${source.id}?${next}`;
  };
  const c = source.counts;

  return (
    <div className="space-y-5">
      <div>
        <Link to="/seller/sources" className="text-brand-700 text-sm hover:underline">
          ← {t("src.nav")}
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <PageTitle
              subtitle={[t(`src.kind.${source.kind}` as TKey), source.supplier_name]
                .filter(Boolean)
                .join(" · ")}
            >
              {source.name}
            </PageTitle>
            <SourceStatusBadge source={source} />
          </div>
          <div className="flex gap-2">
            <Form method="post">
              <Button
                type="submit"
                name="intent"
                value="sync"
                disabled={running}
                loading={nav.formData?.get("intent") === "sync"}
              >
                <RefreshCw className="size-4" aria-hidden /> {t("src.sync")}
              </Button>
            </Form>
            <ButtonLink to={`/seller/sources/${source.id}/edit`} variant="secondary">
              <Settings className="size-4" aria-hidden /> {t("src.detail.edit")}
            </ButtonLink>
          </div>
        </div>
        <p className="text-muted text-sm">
          {t("src.detail.lastSync", {
            date: source.last_sync_at ? formatDateTime(source.last_sync_at, lang) : t("src.never"),
          })}
          {source.next_sync_at &&
            ` · ${t("src.detail.next", { date: formatDateTime(source.next_sync_at, lang) })}`}
        </p>
      </div>

      {running && <Alert>{t("src.running")}</Alert>}
      {source.last_status === "error" && source.last_error && (
        <Alert tone="danger">{source.last_error}</Alert>
      )}
      {actionData?.message && <Alert tone={actionData.ok ? "success" : "danger"}>{actionData.message}</Alert>}

      {c && (
        <div className="grid gap-3 sm:grid-cols-4">
          <StatCard label={t("src.col.items")} value={c.total} />
          <StatCard label={t("src.items.new")} value={c.new} />
          <StatCard label={t("src.items.linked")} value={c.linked} />
          <StatCard label={t("src.items.onlyMissing")} value={c.missing} />
        </div>
      )}

      <nav className="flex flex-wrap gap-2" aria-label={t("catalog.filters")}>
        {TABS.map((s) => (
          <Link
            key={s}
            to={tabHref(s)}
            className={`rounded-full border px-3 py-1 text-sm ${s === tab ? "border-brand-500 bg-brand-50 text-brand-700 font-medium" : "border-line hover:border-brand-500 bg-white"}`}
          >
            {t(`src.items.${s}` as TKey)}
          </Link>
        ))}
      </nav>

      <Form method="get" className="flex flex-wrap items-center gap-3">
        <input type="hidden" name="status" value={tab} />
        <Input
          name="q"
          defaultValue={params.get("q") ?? ""}
          placeholder={t("src.items.search")}
          className="w-64 py-2"
          aria-label={t("nav.search")}
        />
        <Select
          name="category"
          defaultValue={params.get("category") ?? ""}
          className="w-56 py-2"
          aria-label={t("src.items.category")}
        >
          <option value="">{t("src.items.allCategories")}</option>
          {supplierCategories
            .filter((sc) => sc.category_name)
            .map((sc) => (
              <option key={sc.category_name} value={sc.category_name}>
                {sc.category_name} ({sc.total})
              </option>
            ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="available"
            value="1"
            defaultChecked={params.get("available") === "1"}
            className="accent-brand-600 size-4"
          />
          {t("src.items.onlyAvailable")}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="missing"
            value="1"
            defaultChecked={params.get("missing") === "1"}
            className="accent-brand-600 size-4"
          />
          {t("src.items.onlyMissing")}
        </label>
        <Button type="submit" variant="secondary" size="sm">
          {t("common.show")}
        </Button>
      </Form>

      {items.results.length === 0 ? (
        <EmptyState icon={RotateCcw} title={t("src.items.empty")}>
          {c?.total ? null : t("src.items.emptyText")}
        </EmptyState>
      ) : (
        <ItemsTable
          key={items.results.map((i) => i.id).join(",")}
          items={items.results}
          tab={tab}
          categories={categories}
        />
      )}
      <Pagination page={page} pages={pages} />

      {runs.length > 0 && (
        <Card className="p-5">
          <h2 className="mb-3 font-semibold">{t("src.runs")}</h2>
          <ul className="divide-line divide-y">
            {runs.map((run) => (
              <li key={run.id} className="py-2.5 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <RunStatusBadge status={run.status} />
                  <span className="text-muted">{formatDateTime(run.created_at, lang)}</span>
                </div>
                {run.status === "done" && (
                  <p className="text-muted mt-1">
                    {t("src.run.stats", {
                      total: run.stats.total ?? 0,
                      new: run.stats.new ?? 0,
                      changed: run.stats.changed ?? 0,
                      missing: run.stats.missing ?? 0,
                      linked_auto: run.stats.linked_auto ?? 0,
                      price_changed: run.stats.price_changed ?? 0,
                    })}
                  </p>
                )}
                {run.stats.columns && Object.keys(run.stats.columns).length > 0 && (
                  <p className="text-muted mt-1 text-xs">
                    {t("imp.run.columns", {
                      columns: Object.entries(run.stats.columns)
                        .map(([f, col]) => `${t(`src.field.${f}` as TKey)} ← ${col}`)
                        .join(", "),
                    })}
                  </p>
                )}
                {run.error && <p className="text-danger mt-1">{run.error}</p>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
