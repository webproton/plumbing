const money = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 2, minimumFractionDigits: 0 });

/** «1 500,5 ₴» */
export function formatPrice(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? `${money.format(n)} ₴` : "—";
}

/** Количество без лишних нулей: "2.000" → "2", "0.500" → "0,5" */
export function formatQty(value: string | number): string {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 3 }).format(n) : String(value);
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("ru-UA", { day: "2-digit", month: "long", year: "numeric" }).format(new Date(iso));
}

export function pluralize(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}

/** Цвет бейджа статуса заказа */
export function statusTone(status: string): "success" | "danger" | "info" {
  if (status === "completed" || status === "delivered") return "success";
  if (status === "canceled") return "danger";
  return "info";
}
