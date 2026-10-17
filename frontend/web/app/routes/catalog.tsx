import { PackageSearch, SlidersHorizontal } from "lucide-react";
import { Form, Link, useNavigation, useSubmit } from "react-router";

import { Pagination } from "~/components/Pagination";
import { ProductCard } from "~/components/ProductCard";
import { Button, EmptyState, Input, PageTitle, Select } from "~/components/ui";
import { apiContext } from "~/lib/context.server";
import { pluralize } from "~/lib/format";
import type { Paginated, ProductListItem } from "~/lib/types";
import { useRootData } from "~/root";

import type { Route } from "./+types/catalog";

const PAGE_SIZE = 24;
const SORTS = [
  { value: "", label: "Сначала дешёвые" },
  { value: "-price", label: "Сначала дорогие" },
  { value: "new", label: "Новинки" },
  { value: "name", label: "По названию" },
];

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
  const root = matches[0]?.loaderData as { categories?: { slug: string; name: string }[]; siteName?: string } | undefined;
  const category = root?.categories?.find((c) => c.slug === loaderData?.filters.category);
  const title = loaderData?.filters.search
    ? `Поиск «${loaderData.filters.search}»`
    : category?.name ?? "Каталог";
  return [
    { title: `${title} — ${root?.siteName ?? ""}` },
    { name: "description", content: `${title}: цены, наличие на складе, доставка по Украине.` },
  ];
}

export default function Catalog({ loaderData }: Route.ComponentProps) {
  const { results, count, page, pages, filters } = loaderData;
  const categories = useRootData()?.categories ?? [];
  const submit = useSubmit();
  const navigation = useNavigation();
  const loading = navigation.state === "loading" && navigation.location?.pathname === "/catalog";
  const category = categories.find((c) => c.slug === filters.category);

  return (
    <div>
      <PageTitle subtitle={`${count} ${pluralize(count, ["товар", "товара", "товаров"])}`}>
        {filters.search ? `Поиск: «${filters.search}»` : category?.name ?? "Каталог"}
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
            <SlidersHorizontal className="size-4" aria-hidden /> Фильтры
          </p>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Поиск</span>
            <Input name="search" type="search" defaultValue={filters.search} placeholder="Название или артикул" autoFocus={false} />
          </label>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Категория</span>
            <Select name="category" defaultValue={filters.category}>
              <option value="">Все категории</option>
              {categories.map((c) => (
                <option key={c.id} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </Select>
          </label>
          <fieldset className="space-y-1.5">
            <legend className="text-sm font-medium">Цена, ₴</legend>
            <div className="flex gap-2">
              <Input name="min_price" type="number" min={0} inputMode="numeric" placeholder="от" defaultValue={filters.min_price} />
              <Input name="max_price" type="number" min={0} inputMode="numeric" placeholder="до" defaultValue={filters.max_price} />
            </div>
          </fieldset>
          <label className="block space-y-1.5">
            <span className="text-sm font-medium">Сортировка</span>
            <Select name="ordering" defaultValue={filters.ordering}>
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </label>
          <Button type="submit" variant="secondary" className="w-full">
            Показать
          </Button>
          {(filters.search || filters.category || filters.min_price || filters.max_price) && (
            <Link to="/catalog" className="block text-center text-sm text-brand-600 hover:underline">
              Сбросить фильтры
            </Link>
          )}
        </Form>

        <section aria-busy={loading} className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
          {results.length === 0 ? (
            <EmptyState icon={PackageSearch} title="Ничего не нашлось">
              Попробуйте изменить фильтры или поискать по артикулу.
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
