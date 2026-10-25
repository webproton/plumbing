import { PackageSearch, SlidersHorizontal } from "lucide-react";
import { Form, useNavigation, useSubmit } from "react-router";

import { Pagination } from "~/components/Pagination";
import { ProductCard } from "~/components/ProductCard";
import { Button, EmptyState, Input, PageTitle, Select } from "~/components/ui";
import { localizePath, makeT } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { apiContext } from "~/lib/context.server";
import { pluralize } from "~/lib/format";
import { breadcrumbJsonLd } from "~/lib/seo";
import type { Paginated, ProductListItem } from "~/lib/types";
import { useRootData, type RootData } from "~/root";

import type { Route } from "./+types/catalog";

const PAGE_SIZE = 24;
const SORTS = [
  { value: "", label: "catalog.sort.cheap" },
  { value: "-price", label: "catalog.sort.expensive" },
  { value: "new", label: "catalog.sort.new" },
  { value: "name", label: "catalog.sort.name" },
] as const;

export async function loader({ request, context }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const params = url.searchParams;
  const page = Math.max(1, Number(params.get("page")) || 1);
  const filters = {
    category: params.get("category") ?? "",
    search: params.get("search") ?? "",
    ordering: params.get("ordering") ?? "",
    min_price: params.get("min_price") ?? "",
    max_price: params.get("max_price") ?? "",
  };
  const api = context.get(apiContext);
  const data = await api.get<Paginated<ProductListItem>>("/products/", {
    query: { ...filters, page, page_size: PAGE_SIZE },
  }).catch((e) => {
    // несуществующая страница / неверный фильтр — пустой результат, а не ошибка
    if (e?.status === 404 || e?.status === 400) return { count: 0, next: null, previous: null, results: [] };
    throw e;
  });
  return { ...data, page, pages: Math.ceil(data.count / PAGE_SIZE), filters };
}

export function meta({ loaderData, matches }: Route.MetaArgs) {
  const root = matches[0]?.loaderData as RootData | undefined;
  const lang = root?.lang ?? "uk";
  const t = makeT(lang);
  const category = root?.categories?.find((c) => c.slug === loaderData?.filters.category);
  const title = loaderData?.filters.search
    ? t("catalog.searchMeta", { query: loaderData.filters.search })
    : (category?.name ?? t("catalog.title"));
  // у каждой страницы списка — свой заголовок (иначе Google видит дубли «Змішувачі», «Змішувачі»…)
  const page = loaderData && loaderData.page > 1 ? ` — ${t("seo.page", { n: loaderData.page })}` : "";
  const description = t("catalog.metaDescription", { title });
  const origin = root?.publicUrl ?? "";
  return [
    { title: `${title}${page} — ${root?.siteName ?? ""}` },
    { name: "description", content: description },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
    { property: "og:type", content: "website" },
    ...(category
      ? [
          {
            "script:ld+json": breadcrumbJsonLd([
              { name: t("seo.home"), url: `${origin}${localizePath(lang, "/")}` },
              { name: t("catalog.title"), url: `${origin}${localizePath(lang, "/catalog")}` },
              { name: category.name, url: `${origin}${localizePath(lang, `/catalog?category=${category.slug}`)}` },
            ]),
          },
        ]
      : []),
  ];
}

export default function Catalog({ loaderData }: Route.ComponentProps) {
  const { results, count, page, pages, filters } = loaderData;
  const categories = useRootData()?.categories ?? [];
  const t = useT();
  const submit = useSubmit();
  const navigation = useNavigation();
  const loading = navigation.state === "loading" && navigation.location?.pathname === "/catalog";
  const category = categories.find((c) => c.slug === filters.category);

  return (
    <div>
      <PageTitle subtitle={`${count} ${pluralize(count, t("plural.product"))}`}>
        {filters.search ? t("catalog.searchTitle", { query: filters.search }) : (category?.name ?? t("catalog.title"))}
      </PageTitle>

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <Form
          method="get"
          className="space-y-5 self-start rounded-2xl border border-line bg-white p-4 lg:sticky lg:top-24"
          onChange={(e) => {
            // списки применяются сразу, текстовые поля — по Enter или кнопке
            if ((e.target as HTMLElement).tagName === "SELECT") {
              submit(e.currentTarget, { preventScrollReset: true, replace: true });
            }
          }}
        >
          <p className="flex items-center gap-2 font-semibold">
            <SlidersHorizontal className="size-4" aria-hidden /> {t("catalog.filters")}
          </p>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">{t("catalog.search")}</span>
            <Input name="search" type="search" defaultValue={filters.search} placeholder={t("catalog.searchPlaceholder")} autoFocus={false} />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">{t("catalog.category")}</span>
            <Select name="category" defaultValue={filters.category}>
              <option value="">{t("catalog.allCategories")}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </Select>
          </label>
          <fieldset className="space-y-1.5">
            <legend className="text-sm font-medium">{t("catalog.price")}</legend>
            <div className="flex gap-2">
              <Input name="min_price" type="number" min={0} inputMode="numeric" placeholder={t("catalog.priceFrom")} defaultValue={filters.min_price} />
              <Input name="max_price" type="number" min={0} inputMode="numeric" placeholder={t("catalog.priceTo")} defaultValue={filters.max_price} />
            </div>
          </fieldset>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">{t("catalog.sort")}</span>
            <Select name="ordering" defaultValue={filters.ordering}>
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {t(s.label)}
                </option>
              ))}
            </Select>
          </label>
          <Button type="submit" variant="secondary" className="w-full">
            {t("common.show")}
          </Button>
          {(filters.search || filters.category || filters.min_price || filters.max_price) && (
            <Link to="/catalog" className="block text-center text-sm text-brand-600 hover:underline">
              {t("catalog.reset")}
            </Link>
          )}
        </Form>

        <section aria-busy={loading} className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
          {results.length === 0 ? (
            <EmptyState icon={PackageSearch} title={t("catalog.empty.title")}>
              {t("catalog.empty.text")}
            </EmptyState>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
              {results.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          )}
          <Pagination page={page} pages={pages} />
        </section>
      </div>
    </div>
  );
}
