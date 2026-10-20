import { Check, ShoppingCart } from "lucide-react";
import { useFetcher } from "react-router";

import { useLocalPath, useT } from "~/i18n/react";
import { trackEvent, type TrackItem } from "~/lib/analytics";

import { Button } from "./ui";

/** Добавление в корзину без перезагрузки страницы (fetcher → action /cart) */
export function AddToCartButton({
  productId,
  variantId,
  quantity = 1,
  disabled,
  size = "md",
  className,
  track,
}: {
  productId: number;
  variantId: number;
  quantity?: number;
  disabled?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
  /** данные для события add_to_cart в аналитике */
  track?: Omit<TrackItem, "quantity">;
}) {
  const t = useT();
  const local = useLocalPath();
  const fetcher = useFetcher<{ ok?: boolean; error?: string }>();
  const busy = fetcher.state !== "idle";
  const added = fetcher.state === "idle" && fetcher.data?.ok;
  return (
    <fetcher.Form
      method="post"
      action={local("/cart")}
      className={className}
      onSubmit={() => track && trackEvent("add_to_cart", { items: [{ ...track, quantity }] })}
    >
      <input type="hidden" name="intent" value="add" />
      <input type="hidden" name="product" value={productId} />
      <input type="hidden" name="variant" value={variantId} />
      <input type="hidden" name="quantity" value={quantity} />
      <Button type="submit" size={size} loading={busy} disabled={disabled} className="w-full">
        {added ? <Check className="size-4" aria-hidden /> : <ShoppingCart className="size-4" aria-hidden />}
        {disabled ? t("product.outOfStock") : added ? t("cart.added") : t("cart.add")}
      </Button>
      {fetcher.data?.error && <p className="mt-2 text-sm text-danger">{fetcher.data.error}</p>}
    </fetcher.Form>
  );
}
