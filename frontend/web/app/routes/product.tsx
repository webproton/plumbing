import { Clock, Heart, ImageOff, PackageCheck, PackageX, Truck } from "lucide-react";
import { useEffect, useState } from "react";
import { data, useFetcher, useSearchParams } from "react-router";

import { AddToCartButton } from "~/components/AddToCartButton";
import { Price } from "~/components/Price";
import { QuantityStepper } from "~/components/QuantityStepper";
import { Badge, Button } from "~/components/ui";
import { langFromRequest, localizePath, makeT, type TFunction } from "~/i18n";
import { Link, useLocalPath, useT } from "~/i18n/react";
import { trackEvent } from "~/lib/analytics";
import { availabilityOf, onOrderLabel, orderableQty } from "~/lib/availability";
import { ApiError } from "~/lib/api.server";
import { apiContext } from "~/lib/context.server";
import { formatQty } from "~/lib/format";
import { breadcrumbJsonLd, plainText } from "~/lib/seo";
import type { ProductDetail, Variant } from "~/lib/types";
import { thumb } from "~/lib/thumb";
import { useRootData, type RootData } from "~/root";

import type { Route } from "./+types/product";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const api = context.get(apiContext);
  try {
    const product = await api.get<ProductDetail>(`/products/${encodeURIComponent(params.slug)}/`);
    return { product };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data(makeT(langFromRequest(request))("product.notFound"), { status: 404 });
    throw e;
  }
}

export function meta({ loaderData, matches }: Route.MetaArgs) {
  const root = matches[0]?.loaderData as RootData | undefined;
  const lang = root?.lang ?? "uk";
  const t = makeT(lang);
  if (!loaderData) return [{ title: t("product.notFound") }];
  const { product } = loaderData;
  const v = product.variants[0];
  const origin = root?.publicUrl ?? "";
  const image = v?.photo ?? product.photo;
  const imageUrl = image ? (/^https?:\/\//.test(image) ? image : `${origin}${image}`) : undefined;
  const url = `${origin}${localizePath(lang, `/product/${product.slug}`)}`;
  const description =
    plainText(product.description ?? v?.description) || t("product.metaDescription", { name: product.name });
  const crumbs = [
    { name: t("seo.home"), url: `${origin}${localizePath(lang, "/")}` },
    ...(product.category
      ? [{ name: product.category.name, url: `${origin}${localizePath(lang, `/catalog?category=${product.category.slug}`)}` }]
      : [{ name: t("catalog.title"), url: `${origin}${localizePath(lang, "/catalog")}` }]),
    { name: product.name, url },
  ];
  return [
    { title: t("product.metaTitle", { name: product.name, site: root?.siteName ?? "" }) },
    { name: "description", content: description },
    { property: "og:title", content: product.name },
    { property: "og:description", content: description },
    { property: "og:type", content: "product" },
    ...(imageUrl ? [{ property: "og:image", content: imageUrl }] : []),
    ...(v?.price
      ? [
          { property: "product:price:amount", content: String(v.price) },
          { property: "product:price:currency", content: "UAH" },
        ]
      : []),
    {
      "script:ld+json": {
        "@context": "https://schema.org",
        "@type": "Product",
        name: product.name,
        sku: v?.code ?? undefined,
        image: imageUrl,
        description,
        category: product.category?.name ?? undefined,
        offers: v?.price
          ? {
              "@type": "Offer",
              url,
              price: v.price,
              priceCurrency: "UAH",
              itemCondition: "https://schema.org/NewCondition",
              availability: v.in_stock
                ? "https://schema.org/InStock"
                : v.on_order
                  ? "https://schema.org/BackOrder"
                  : "https://schema.org/OutOfStock",
            }
          : undefined,
      },
    },
    { "script:ld+json": breadcrumbJsonLd(crumbs) },
  ];
}

function variantLabel(v: Variant, t: TFunction) {
  return v.color?.name ?? v.product_name ?? v.code ?? t("product.variantN", { n: v.id });
}

export default function ProductPage({ loaderData }: Route.ComponentProps) {
  const { product } = loaderData;
  const [params, setParams] = useSearchParams();
  const user = useRootData()?.user;
  const t = useT();
  const variant =
    product.variants.find((v) => String(v.id) === params.get("v")) ?? product.variants[0] ?? null;
  const [qty, setQty] = useState(1);
  useEffect(() => {
    if (variant) trackEvent("view_item", { items: [{ id: variant.id, name: product.name, price: Number(variant.price ?? 0) }] });
  }, [variant, product.name]);
  const images = [variant?.photo, product.photo, ...product.photos.map((p) => p.photo)].filter(
    (src, i, all): src is string => Boolean(src) && all.indexOf(src) === i,
  );
  const [active, setActive] = useState(0);
  const available = variant ? Number(variant.available_qty) : 0;
  const availability = availabilityOf(variant);

  return (
    <div className="space-y-10">
      <nav aria-label={t("nav.catalog")} className="text-sm text-muted">
        <Link to="/catalog" className="hover:text-ink">{t("nav.catalog")}</Link>
        {product.category && (
          <>
            {" / "}
            <Link to={`/catalog?category=${product.category.slug}`} className="hover:text-ink">
              {product.category.name}
            </Link>
          </>
        )}
      </nav>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="grid aspect-square place-items-center overflow-hidden rounded-3xl border border-line bg-white">
            {images[active] ? (
              <img src={thumb(images[active], 800)} alt={product.name} className="size-full object-contain p-6" />
            ) : (
              <ImageOff className="size-12 text-muted" aria-hidden />
            )}
          </div>
          {images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {images.map((src, i) => (
                <button
                  key={src}
                  type="button"
                  onClick={() => setActive(i)}
                  aria-label={t("product.photo", { n: i + 1 })}
                  aria-pressed={i === active}
                  className={`size-20 shrink-0 overflow-hidden rounded-xl border bg-white ${i === active ? "border-brand-500 ring-2 ring-brand-100" : "border-line"}`}
                >
                  <img src={thumb(src, 160)} alt="" className="size-full object-contain p-1" loading="lazy" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{product.name}</h1>
            {variant?.code && <p className="text-sm text-muted">{t("product.sku", { sku: variant.code })}</p>}
          </div>

          {variant ? (
            <>
              <Price value={variant.price} original={variant.original_price} size="lg" />
              <div className="flex items-center gap-2">
                {availability === "in_stock" ? (
                  <Badge tone="success">
                    <PackageCheck className="mr-1 size-3.5" aria-hidden /> {t("product.inStockQty", { qty: formatQty(available) })}
                  </Badge>
                ) : availability === "on_order" ? (
                  <Badge tone="info">
                    <Clock className="mr-1 size-3.5" aria-hidden /> {onOrderLabel(t, variant.on_order_days)}
                  </Badge>
                ) : (
                  <Badge tone="muted">
                    <PackageX className="mr-1 size-3.5" aria-hidden /> {t("product.outOfStock")}
                  </Badge>
                )}
              </div>
              {availability === "on_order" && variant.on_order_days ? (
                <p className="text-sm text-muted">{t("product.onOrderNote", { days: variant.on_order_days })}</p>
              ) : null}

              {product.variants.length > 1 && (
                <fieldset className="space-y-2">
                  <legend className="text-sm font-medium">{t("product.variant")}</legend>
                  <div className="flex flex-wrap gap-2">
                    {product.variants.map((v) => (
                      <button
                        key={v.id}
                        type="button"
                        onClick={() => {
                          setQty(1);
                          setActive(0);
                          setParams({ v: String(v.id) }, { replace: true, preventScrollReset: true });
                        }}
                        aria-pressed={v.id === variant.id}
                        className={`rounded-xl border px-3 py-2 text-sm ${v.id === variant.id ? "border-brand-500 bg-brand-50 font-medium" : "border-line bg-white hover:border-brand-500"} ${availabilityOf(v) === "out" ? "text-muted" : ""}`}
                      >
                        {variantLabel(v, t)}
                      </button>
                    ))}
                  </div>
                </fieldset>
              )}

              <div className="flex flex-wrap items-center gap-3">
                <QuantityStepper
                  value={qty}
                  onChange={setQty}
                  max={availability === "out" ? undefined : Math.floor(orderableQty(variant))}
                />
                <AddToCartButton
                  productId={product.id}
                  variantId={variant.id}
                  quantity={qty}
                  disabled={availability === "out"}
                  size="lg"
                  className="min-w-48 flex-1"
                  track={{ id: variant.id, name: product.name, price: Number(variant.price ?? 0) }}
                />
                {user && <WishlistButton variantId={variant.id} />}
              </div>

              <p className="flex items-center gap-2 text-sm text-muted">
                <Truck className="size-4" aria-hidden /> {t("product.deliveryNote")}
              </p>
            </>
          ) : (
            <Badge tone="muted">{t("product.unavailable")}</Badge>
          )}

          <Specs variant={variant} />
        </div>
      </div>

      {(variant?.description || product.description || variant?.features) && (
        <section className="max-w-3xl space-y-3">
          <h2 className="text-xl font-bold">{t("product.description")}</h2>
          <p className="leading-relaxed whitespace-pre-line text-ink/90">{variant?.description || product.description}</p>
          {variant?.features && <p className="leading-relaxed whitespace-pre-line text-muted">{variant.features}</p>}
        </section>
      )}
    </div>
  );
}

function Specs({ variant }: { variant: Variant | null }) {
  const t = useT();
  if (!variant) return null;
  const rows: [string, string | null | undefined][] = [
    [t("product.spec.brand"), variant.brand?.name],
    [t("product.spec.color"), variant.color?.name],
    [t("product.spec.width"), variant.dimensions_width],
    [t("product.spec.height"), variant.dimensions_height],
    [t("product.spec.depth"), variant.dimensions_depth],
    [t("product.spec.weight"), variant.dimensions_weight],
    ...Object.entries(variant.attributes ?? {}).map(([k, v]): [string, string] => [k, v == null ? "" : String(v)]),
  ];
  const filled = rows.filter(([, v]) => v).filter(([k], i, list) => list.findIndex(([k2]) => k2 === k) === i);
  if (!filled.length) return null;
  return (
    <dl className="divide-y divide-line rounded-2xl border border-line bg-white">
      {filled.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4 px-4 py-2.5 text-sm">
          <dt className="text-muted">{k}</dt>
          <dd className="text-right font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function WishlistButton({ variantId }: { variantId: number }) {
  const fetcher = useFetcher<{ ok?: boolean }>();
  const t = useT();
  const local = useLocalPath();
  return (
    <fetcher.Form method="post" action={local("/wishlist")}>
      <input type="hidden" name="intent" value="add" />
      <input type="hidden" name="variant" value={variantId} />
      <Button type="submit" variant="secondary" size="lg" aria-label={t("product.toWishlist")} loading={fetcher.state !== "idle"}>
        <Heart className={`size-5 ${fetcher.data?.ok ? "fill-danger text-danger" : ""}`} aria-hidden />
      </Button>
    </fetcher.Form>
  );
}
