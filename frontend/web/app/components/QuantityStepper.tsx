import { Minus, Plus } from "lucide-react";

import { useT } from "~/i18n/react";

/** Поле количества с кнопками ±; работает и без JS (обычный input type=number) */
export function QuantityStepper({
  name = "quantity",
  value,
  onChange,
  max,
  label,
}: {
  name?: string;
  value: number;
  onChange: (value: number) => void;
  max?: number;
  label?: string;
}) {
  const t = useT();
  const clamp = (n: number) => Math.max(1, max ? Math.min(n, max) : n);
  return (
    <div className="inline-flex items-center rounded-xl border border-line bg-white">
      <button
        type="button"
        className="grid size-10 place-items-center text-muted hover:text-ink disabled:opacity-40"
        onClick={() => onChange(clamp(value - 1))}
        disabled={value <= 1}
        aria-label={t("common.decrease")}
      >
        <Minus className="size-4" />
      </button>
      <input
        name={name}
        type="number"
        inputMode="numeric"
        min={1}
        max={max}
        value={value}
        aria-label={label ?? t("common.quantity")}
        onChange={(e) => onChange(clamp(Number(e.target.value) || 1))}
        className="w-12 [appearance:textfield] bg-transparent text-center font-medium focus:outline-none [&::-webkit-inner-spin-button]:appearance-none"
      />
      <button
        type="button"
        className="grid size-10 place-items-center text-muted hover:text-ink disabled:opacity-40"
        onClick={() => onChange(clamp(value + 1))}
        disabled={max !== undefined && value >= max}
        aria-label={t("common.increase")}
      >
        <Plus className="size-4" />
      </button>
    </div>
  );
}
