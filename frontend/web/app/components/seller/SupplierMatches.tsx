import { ImageOff, Package, Plus, Truck } from "lucide-react";
import { Form, useNavigation } from "react-router";

import { Button, ButtonLink } from "~/components/ui";
import { Link, useT } from "~/i18n/react";
import { formatPrice } from "~/lib/format";

export interface SupplierMatch {
  id: number;
  name: string;
  sku: string;
  brand: string;
  source: { id: number; name: string };
  /** new — ещё не товар; linked — уже в каталоге (product_id); ignored — пропущена на странице поставщика */
  status?: "new" | "linked" | "ignored";
  product_id?: number | null;
  /** цена продажи в гривнах по правилам поставщика; null — нет цены или курса валюты */
  price: string | null;
  raw_price: string | null;
  currency: string;
  quantity: string | null;
  available: boolean | null;
  photo: string | null;
}

export interface SupplierSearch {
  count: number;
  results: SupplierMatch[];
  suggestion: string | null;
}

/** Есть у поставщика, но ещё не в каталоге продавца: нашли по поиску в «Товарах» — можно сразу создать товар. */
export function SupplierMatches({
  data,
  query,
  everywhere = false,
}: {
  data: SupplierSearch | null;
  query: string;
  /** поиск кабинета: все загруженные источники, и уже товары тоже */
  everywhere?: boolean;
}) {
  const t = useT();
  const busy = useNavigation().state === "submitting";
  if (!data || data.count === 0) return null;
  return (
    <section className="border-brand-500/60 bg-brand-50/60 space-y-3 rounded-2xl border border-dashed p-4">
      <div className="space-y-1">
        <h2 className="flex items-center gap-2 font-semibold">
          <Truck className="text-brand-600 size-5" aria-hidden />
          {t(everywhere ? "search.sources.title" : "prod.suppliers.title", { n: data.count })}
        </h2>
        <p className="text-muted text-sm">
          {data.suggestion ? t("prod.suppliers.suggested", { query, suggestion: data.suggestion }) + " " : ""}
          {t(everywhere ? "search.sources.hint" : "prod.suppliers.hint")}
        </p>
      </div>
      <ul className="divide-line border-line divide-y overflow-hidden rounded-xl border bg-white">
        {data.results.map((item) => {
          const inStock = item.quantity !== null ? Number(item.quantity) > 0 : item.available;
          return (
            <li key={item.id} className="flex flex-wrap items-center gap-3 p-3">
              {item.photo ? (
                <img
                  src={item.photo}
                  alt=""
                  loading="lazy"
                  className="border-line size-12 shrink-0 rounded-lg border object-contain"
                />
              ) : (
                <span className="bg-surface text-muted grid size-12 shrink-0 place-items-center rounded-lg">
                  <ImageOff className="size-5" aria-hidden />
                </span>
              )}
              <div className="min-w-0 flex-1 basis-48">
                <p className="font-medium">{item.name}</p>
                <p className="text-muted text-xs">
                  {[item.sku, item.brand].filter(Boolean).join(" · ")}
                  {item.sku || item.brand ? " · " : ""}
                  {t("prod.suppliers.from", { name: item.source.name })}
                  {item.status === "linked" && ` · ${t("search.sources.inCatalog")}`}
                  {item.status === "ignored" && ` · ${t("search.sources.ignored")}`}
                  {inStock === true && ` · ${t("prod.suppliers.inStock")}`}
                  {inStock === false && ` · ${t("prod.suppliers.outOfStock")}`}
                </p>
              </div>
              <div className="text-right text-sm">
                {item.price ? (
                  <span className="font-semibold">{formatPrice(item.price)}</span>
                ) : item.raw_price ? (
                  <span>
                    {item.raw_price.replace(/\.?0+$/, "")} {item.currency}
                    <Link
                      to={`/seller/sources/${item.source.id}/edit`}
                      className="text-danger block text-xs hover:underline"
                    >
                      {t("prod.suppliers.noRate", { currency: item.currency })}
                    </Link>
                  </span>
                ) : (
                  "—"
                )}
              </div>
              <div className="flex w-full gap-2 sm:w-auto">
                {item.status === "linked" && item.product_id ? (
                  // уже товар каталога — к его карточке
                  <ButtonLink
                    size="sm"
                    className="flex-1 sm:flex-none"
                    to={`/seller/products/${item.product_id}`}
                  >
                    <Package className="size-4" aria-hidden /> {t("search.sources.openProduct")}
                  </ButtonLink>
                ) : (
                  <Form method="post" className="flex-1 sm:flex-none">
                    <input type="hidden" name="intent" value="publishItem" />
                    <input type="hidden" name="source" value={item.source.id} />
                    <input type="hidden" name="item" value={item.id} />
                    <Button type="submit" size="sm" className="w-full" disabled={!item.price || busy}>
                      <Plus className="size-4" aria-hidden /> {t("prod.suppliers.create")}
                    </Button>
                  </Form>
                )}
                <ButtonLink
                  size="sm"
                  variant="secondary"
                  className="flex-1 sm:flex-none"
                  to={`/seller/sources/${item.source.id}?q=${encodeURIComponent(item.sku || item.name)}`}
                >
                  {t("prod.suppliers.open")}
                </ButtonLink>
              </div>
            </li>
          );
        })}
      </ul>
      {data.count > data.results.length && (
        <p className="text-muted text-sm">
          {t("prod.suppliers.more", { n: data.count - data.results.length })}
        </p>
      )}
    </section>
  );
}
