import { Check, ShoppingCart } from "lucide-react";
import { useFetcher } from "react-router";

import { Button } from "./ui";

/** Добавление в корзину без перезагрузки страницы (fetcher → action /cart) */
export function AddToCartButton({
  productId,
  variantId,
  quantity = 1,
  disabled,
  size = "md",
  className,
}: {
  productId: number;
  variantId: number;
  quantity?: number;
  disabled?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const fetcher = useFetcher<{ ok?: boolean; error?: string }>();
  const busy = fetcher.state !== "idle";
  const added = fetcher.state === "idle" && fetcher.data?.ok;
  return (
    <fetcher.Form method="post" action="/cart" className={className}>
      <input type="hidden" name="intent" value="add" />
      <input type="hidden" name="product" value={productId} />
      <input type="hidden" name="variant" value={variantId} />
      <input type="hidden" name="quantity" value={quantity} />
      <Button type="submit" size={size} loading={busy} disabled={disabled} className="w-full">
        {added ? <Check className="size-4" aria-hidden /> : <ShoppingCart className="size-4" aria-hidden />}
        {disabled ? "Нет в наличии" : added ? "В корзине" : "В корзину"}
      </Button>
      {fetcher.data?.error && <p className="mt-2 text-sm text-danger">{fetcher.data.error}</p>}
    </fetcher.Form>
  );
}
