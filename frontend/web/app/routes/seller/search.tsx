import { ImageOff, Package, Search as SearchIcon } from "lucide-react";
import { Form } from "react-router";

import { SupplierMatches, type SupplierSearch } from "~/components/seller/SupplierMatches";
import { Alert, EmptyState, PageTitle, SearchBox, SuggestionNote } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { formatPrice, formatQty } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";
import { publishSupplierItem } from "~/lib/supplier.server";
import { thumb } from "~/lib/thumb";
import type { ManageProductRow, SearchPage } from "~/lib/types";

import type { Route } from "./+types/search";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("search.cabinet.title") },
];

const OWN_LIMIT = 12;

/** Поиск кабинета: свои товары + все загруженные источники товаров (прайсы, фиды), даже то, чего нет на складе. */
export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  const query = new URL(request.url).searchParams.get("q")?.trim() ?? "";
  if (!query) return { query, own: null, sources: null };
  const [own, sources] = await Promise.all([
    api
      .get<SearchPage<ManageProductRow>>("/manage/products/", { query: { q: query, page_size: OWN_LIMIT } })
      .catch(() => null),
    api
      .get<SupplierSearch>("/imports/sources/search-items/", { query: { q: query, all: 1 } })
      .catch(() => null), // нет доступа к источникам товаров — только свои товары
  ]);
  return { query, own, sources };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  return publishSupplierItem(api, await request.formData(), makeT(langFromRequest(request)));
}

export default function CabinetSearch({ loaderData, actionData }: Route.ComponentProps) {
  const { query, own, sources } = loaderData;
  const t = useT();
  const nothing = query && !own?.count && !sources?.count;

  return (
    <div className="space-y-5">
      <PageTitle subtitle={t("search.cabinet.subtitle")}>{t("search.cabinet.title")}</PageTitle>
      <Form method="get">
        <SearchBox
          key={query}
          name="q"
          defaultValue={query}
          placeholder={t("search.cabinet.placeholder")}
          aria-label={t("nav.search")}
          autoFocus={!query}
          className="w-full"
        />
      </Form>

      {actionData?.message && <Alert tone={actionData.ok ? "success" : "danger"}>{actionData.message}</Alert>}
      {own?.suggestion && <SuggestionNote query={query} suggestion={own.suggestion} />}

      {nothing && (
        <EmptyState icon={SearchIcon} title={t("search.cabinet.nothing", { query })}>
          {t("search.cabinet.nothingText")}
        </EmptyState>
      )}

      {!!own?.count && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="flex items-center gap-2 font-semibold">
              <Package className="text-brand-600 size-5" aria-hidden />{" "}
              {t("search.own.title", { n: own.count })}
            </h2>
            {own.count > own.results.length && (
              <Link
                to={`/seller/products?q=${encodeURIComponent(own.suggestion ?? query)}`}
                className="text-brand-600 text-sm hover:underline"
              >
                {t("search.own.all", { n: own.count })}
              </Link>
            )}
          </div>
          <ul className="divide-line border-line divide-y overflow-hidden rounded-xl border bg-white">
            {own.results.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/seller/products/${p.id}`}
                  className="hover:bg-surface flex items-center gap-3 p-3"
                >
                  {p.photo ? (
                    <img
                      src={thumb(p.photo, 160)}
                      alt=""
                      loading="lazy"
                      className="border-line size-12 shrink-0 rounded-lg border object-contain"
                    />
                  ) : (
                    <span className="bg-surface text-muted grid size-12 shrink-0 place-items-center rounded-lg">
                      <ImageOff className="size-5" aria-hidden />
                    </span>
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{p.name}</span>
                    <span className="text-muted block text-xs">
                      {[p.sku, p.category_name].filter(Boolean).join(" · ")}
                      {p.visible ? ` · ${t("search.own.visible")}` : ` · ${t("search.own.hidden")}`}
                    </span>
                  </span>
                  <span className="text-right text-sm">
                    <span className="block font-semibold">{formatPrice(p.price_min)}</span>
                    <span className="text-muted block text-xs">
                      {t("search.own.stock", { n: formatQty(p.stock) })}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <SupplierMatches data={sources} query={query} everywhere />
    </div>
  );
}
