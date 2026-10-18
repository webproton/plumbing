import { ImageOff } from "lucide-react";
import { Link, useT } from "~/i18n/react";

import type { ProductListItem } from "~/lib/types";

import { AddToCartButton } from "./AddToCartButton";
import { Price } from "./Price";
import { Badge } from "./ui";

export function ProductCard({ product }: { product: ProductListItem }) {
  const t = useT();
  const variant = product.first_variant;
  const image = variant?.photo ?? product.photo;
  const inStock = Boolean(variant?.in_stock);
  return (
    <article className="group flex flex-col overflow-hidden rounded-[var(--radius-card)] border border-line bg-white transition-shadow hover:shadow-lg">
      <Link to={`/product/${product.slug}`} prefetch="intent" className="relative block aspect-square bg-surface">
        {image ? (
          <img
            src={image}
            alt={product.name}
            loading="lazy"
            className="size-full object-contain p-4 transition-transform group-hover:scale-105"
          />
        ) : (
          <ImageOff className="absolute inset-0 m-auto size-10 text-muted" aria-hidden />
        )}
        {variant && variant.discount > 0 && (
          <span className="absolute top-3 left-3 rounded-full bg-danger px-2 py-0.5 text-xs font-semibold text-white">
            −{variant.discount}%
          </span>
        )}
      </Link>
      <div className="flex flex-1 flex-col gap-3 p-4">
        {product.category && <span className="text-xs text-muted">{product.category}</span>}
        <Link to={`/product/${product.slug}`} prefetch="intent" className="line-clamp-2 font-medium hover:text-brand-600">
          {product.name}
        </Link>
        <div className="mt-auto flex items-end justify-between gap-2">
          <Price value={product.price} original={variant?.original_price} from />
          <Badge tone={inStock ? "success" : "muted"}>{inStock ? t("product.inStock") : t("product.onOrder")}</Badge>
        </div>
        {variant && <AddToCartButton productId={product.id} variantId={variant.id} disabled={!inStock} size="sm" />}
      </div>
    </article>
  );
}
