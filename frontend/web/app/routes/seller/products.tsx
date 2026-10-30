import { Eye, EyeOff, FolderInput, ImageOff, Package, Plus, Printer } from "lucide-react";
import { useState } from "react";
import { data, Form, useNavigation, useSearchParams } from "react-router";

import { Pagination } from "~/components/Pagination";
import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  buttonClass,
  EmptyState,
  Input,
  PageTitle,
  Select,
} from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TKey } from "~/i18n";
import { Link, useLocalPath, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { formatPrice, formatQty, pluralize } from "~/lib/format";
import { pageOf, pagesOf, paged, requireSeller } from "~/lib/seller.server";
import type { Category, ManageProductRow, Paginated } from "~/lib/types";
import { thumb } from "~/lib/thumb";

import type { Route } from "./+types/products";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("prod.nav") }];

const SORTS = ["updated", "new", "name", "price", "-price"] as const;

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const q = new URL(request.url).searchParams;
  const page = pageOf(request);
  const [products, categories] = await Promise.all([
    paged(
      api.get<Paginated<ManageProductRow>>("/manage/products/", {
        query: {
          q: q.get("q") || undefined,
          category: q.get("category") || undefined,
          visible: q.get("visible") || undefined,
          no_photo: q.get("no_photo") || undefined,
          in_stock: q.get("in_stock") || undefined,
          ordering: q.get("ordering") || undefined,
          page,
        },
      }),
    ),
    api.get<Category[]>("/category/"),
  ]);
  return { ...products, page, pages: pagesOf(products), categories };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const ids = form.getAll("ids").map(Number).filter(Boolean);
  const kind = String(form.get("intent"));
  try {
    const r = await api.post<{ changed: number }>("/manage/products/bulk/", {
      ids,
      action: kind,
      category: kind === "category" ? Number(form.get("category")) || null : undefined,
    });
    return { ok: true as const, message: t("prod.bulk.done", { n: r.changed }) };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, message: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
}

function Rows({ results, categories }: { results: ManageProductRow[]; categories: Category[] }) {
  const t = useT();
  const local = useLocalPath();
  const busy = useNavigation().state === "submitting";
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const labels = (size: "thermal" | "a4") =>
    local(`/seller/labels?products=${[...selected].join(",")}&size=${size}`);
  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const all = results.every((p) => selected.has(p.id));

  return (
    <div className="space-y-3">
      <Form
        id="bulk"
        method="post"
        className="border-line flex flex-wrap items-center gap-2 rounded-2xl border bg-white p-3"
      >
        <span className="text-sm font-medium">{t("src.bulk.selected", { n: selected.size })}</span>
        <Button
          type="submit"
          name="intent"
          value="show"
          size="sm"
          variant="secondary"
          disabled={!selected.size}
          loading={busy}
        >
          <Eye className="size-3.5" aria-hidden /> {t("prod.bulk.show")}
        </Button>
        <Button
          type="submit"
          name="intent"
          value="hide"
          size="sm"
          variant="secondary"
          disabled={!selected.size}
        >
          <EyeOff className="size-3.5" aria-hidden /> {t("prod.bulk.hide")}
        </Button>
        <Select
          name="category"
          defaultValue=""
          className="w-52 py-1.5 text-sm"
          aria-label={t("prod.bulk.toCategory")}
        >
          <option value="">{t("prod.bulk.toCategory")}</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Button
          type="submit"
          name="intent"
          value="category"
          size="sm"
          variant="secondary"
          disabled={!selected.size}
        >
          <FolderInput className="size-3.5" aria-hidden /> {t("prod.bulk.category")}
        </Button>
        {selected.size > 0 && (
          <>
            <a
              href={labels("thermal")}
              target="_blank"
              rel="noreferrer"
              className={buttonClass("ghost", "sm")}
            >
              <Printer className="size-3.5" aria-hidden /> {t("prod.labels.thermal")}
            </a>
            <a href={labels("a4")} target="_blank" rel="noreferrer" className={buttonClass("ghost", "sm")}>
              <Printer className="size-3.5" aria-hidden /> {t("prod.labels.a4")}
            </a>
          </>
        )}
      </Form>
      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th className="w-10">
                <input
                  type="checkbox"
                  checked={all}
                  onChange={() => setSelected(all ? new Set() : new Set(results.map((p) => p.id)))}
                  aria-label={t("src.bulk.selectAll")}
                  className="accent-brand-600 size-4"
                />
              </Th>
              <Th>{t("wh.col.product")}</Th>
              <Th>{t("prod.col.category")}</Th>
              <Th align="right">{t("prod.col.price")}</Th>
              <Th align="right">{t("prod.col.stock")}</Th>
              <Th>{t("prod.visibility")}</Th>
            </tr>
          </thead>
          <tbody>
            {results.map((p) => (
              <tr key={p.id} className="hover:bg-surface">
                <Td>
                  <input
                    type="checkbox"
                    form="bulk"
                    name="ids"
                    value={p.id}
                    checked={selected.has(p.id)}
                    onChange={() => toggle(p.id)}
                    aria-label={p.name}
                    className="accent-brand-600 size-4"
                  />
                </Td>
                <Td className="min-w-64">
                  <Link to={`/seller/products/${p.id}`} className="flex items-center gap-3">
                    {p.photo ? (
                      <img
                        src={thumb(p.photo, 160)}
                        alt=""
                        loading="lazy"
                        className="border-line size-11 shrink-0 rounded-lg border object-contain"
                      />
                    ) : (
                      <span className="bg-surface text-muted flex size-11 shrink-0 items-center justify-center rounded-lg">
                        <ImageOff className="size-4" aria-hidden />
                      </span>
                    )}
                    <span className="min-w-0">
                      <span className="text-brand-700 block font-medium hover:underline">{p.name}</span>
                      <span className="text-muted block text-xs">
                        {[
                          p.sku,
                          p.variants_count > 1
                            ? `${p.variants_count} ${pluralize(p.variants_count, t("prod.variants"))}`
                            : "",
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </span>
                  </Link>
                </Td>
                <Td className="text-muted">{p.category_name ?? "—"}</Td>
                <Td align="right" className="whitespace-nowrap">
                  {p.price_min
                    ? `${p.variants_count > 1 ? t("common.currencyFrom") : ""}${formatPrice(p.price_min)}`
                    : "—"}
                </Td>
                <Td align="right">{formatQty(p.stock)}</Td>
                <Td>
                  {p.visible ? (
                    <Badge tone="success">{t("prod.visible")}</Badge>
                  ) : (
                    <Badge tone="muted">{t("prod.hidden")}</Badge>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </TableWrap>
    </div>
  );
}

export default function Products({ loaderData, actionData }: Route.ComponentProps) {
  const { results, page, pages, categories } = loaderData;
  const t = useT();
  const [params] = useSearchParams();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageTitle subtitle={t("prod.subtitle")} help="products">{t("prod.nav")}</PageTitle>
        <ButtonLink to="/seller/products/new">
          <Plus className="size-4" aria-hidden /> {t("prod.add")}
        </ButtonLink>
      </div>

      <Form method="get" className="flex flex-wrap items-center gap-3">
        <Input
          name="q"
          defaultValue={params.get("q") ?? ""}
          placeholder={t("prod.search")}
          className="w-64 py-2"
          aria-label={t("nav.search")}
        />
        <Select
          name="category"
          defaultValue={params.get("category") ?? ""}
          className="w-52 py-2"
          aria-label={t("prod.col.category")}
        >
          <option value="">{t("prod.allCategories")}</option>
          <option value="none">{t("prod.noCategory")}</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Select
          name="visible"
          defaultValue={params.get("visible") ?? ""}
          className="w-40 py-2"
          aria-label={t("prod.visibility")}
        >
          <option value="">{t("prod.visibility.all")}</option>
          <option value="1">{t("prod.visibility.visible")}</option>
          <option value="0">{t("prod.visibility.hidden")}</option>
        </Select>
        <Select
          name="ordering"
          defaultValue={params.get("ordering") ?? "updated"}
          className="w-48 py-2"
          aria-label={t("catalog.sort")}
        >
          {SORTS.map((s) => (
            <option key={s} value={s}>
              {t(`prod.sort.${s}` as TKey)}
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="no_photo"
            value="1"
            defaultChecked={params.get("no_photo") === "1"}
            className="accent-brand-600 size-4"
          />
          {t("prod.noPhoto")}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="in_stock"
            value="1"
            defaultChecked={params.get("in_stock") === "1"}
            className="accent-brand-600 size-4"
          />
          {t("prod.inStock")}
        </label>
        <Button type="submit" variant="secondary" size="sm">
          {t("common.show")}
        </Button>
      </Form>

      {actionData?.message && <Alert tone={actionData.ok ? "success" : "danger"}>{actionData.message}</Alert>}

      {results.length === 0 ? (
        <EmptyState icon={Package} title={t("prod.empty")}>
          {t("prod.emptyText")}
        </EmptyState>
      ) : (
        <>
          <Rows key={results.map((p) => p.id).join(",")} results={results} categories={categories} />
          <Pagination page={page} pages={pages} />
        </>
      )}
    </div>
  );
}
