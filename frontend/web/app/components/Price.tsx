import { formatPrice } from "~/lib/format";

export function Price({
  value,
  original,
  from = false,
  size = "md",
}: {
  value: string | number | null;
  original?: string | number | null;
  from?: boolean;
  size?: "md" | "lg";
}) {
  const hasDiscount = original && Number(original) > Number(value);
  return (
    <div className="flex items-baseline gap-2">
      <span className={size === "lg" ? "text-3xl font-bold" : "text-lg font-semibold"}>
        {from && value ? "от " : ""}
        {formatPrice(value)}
      </span>
      {hasDiscount && <span className="text-sm text-muted line-through">{formatPrice(original)}</span>}
    </div>
  );
}
