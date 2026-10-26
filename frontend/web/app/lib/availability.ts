import type { TFunction } from "~/i18n";

import type { Variant } from "./types";

export type Availability = "in_stock" | "on_order" | "out";

type Stock = Pick<Variant, "in_stock" | "on_order" | "available_qty" | "orderable_qty">;

/** Свій склад важливіший: «під замовлення» — лише коли свого немає, а в постачальника є. */
export function availabilityOf(v: Pick<Stock, "in_stock" | "on_order"> | null | undefined): Availability {
  if (!v) return "out";
  if (v.in_stock) return "in_stock";
  return v.on_order ? "on_order" : "out";
}

/** Скільки можна покласти в кошик: свій залишок або, якщо більше, — під замовлення. */
export function orderableQty(v: Stock): number {
  return Number(v.orderable_qty ?? v.available_qty ?? 0);
}

export function onOrderLabel(t: TFunction, days: number | null | undefined): string {
  return days ? t("product.onOrderDays", { days }) : t("product.onOrder");
}
