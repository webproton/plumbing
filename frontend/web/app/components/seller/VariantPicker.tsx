import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useFetcher } from "react-router";

import { useLocalPath, useT } from "~/i18n/react";
import { formatQty } from "~/lib/format";
import type { VariantLookup } from "~/lib/types";

import { Input } from "../ui";

/** Поиск товара по названию/артикулу/штрихкоду. Выбранный id уходит в форму полем `name`. */
export function VariantPicker({
  name = "variant",
  error,
  onSelect,
  initial,
}: {
  name?: string;
  error?: string;
  onSelect?: (variant: VariantLookup | null) => void;
  initial?: VariantLookup | null;
}) {
  const t = useT();
  const local = useLocalPath();
  const fetcher = useFetcher<VariantLookup[]>();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<VariantLookup | null>(initial ?? null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    clearTimeout(timer.current);
    if (selected || query.trim().length < 2) return;
    timer.current = setTimeout(() => fetcher.load(local(`/seller/variants?q=${encodeURIComponent(query.trim())}`)), 250);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, selected]);

  const choose = (v: VariantLookup | null) => {
    setSelected(v);
    setQuery("");
    onSelect?.(v);
  };

  if (selected) {
    return (
      <div className="flex items-start justify-between gap-3 rounded-xl border border-brand-500 bg-brand-50 p-3">
        <input type="hidden" name={name} value={selected.id} />
        <div className="min-w-0">
          <p className="font-medium">{selected.name}</p>
          <p className="text-sm text-muted">
            {selected.sku && `${selected.sku} · `}
            {selected.barcode && `${selected.barcode} · `}
            {t("wh.picker.available", { qty: formatQty(selected.available) })}
          </p>
        </div>
        <button type="button" onClick={() => choose(null)} className="text-muted hover:text-ink" aria-label={t("wh.picker.change")}>
          <X className="size-5" />
        </button>
      </div>
    );
  }

  const results = fetcher.data ?? [];
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("wh.picker.placeholder")}
        aria-label={t("wh.col.product")}
        aria-invalid={Boolean(error)}
        autoComplete="off"
        className="pl-9"
      />
      {error && <p className="mt-1.5 text-sm text-danger">{error}</p>}
      {query.trim().length >= 2 && fetcher.state === "idle" && fetcher.data && (
        <ul className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-line bg-white shadow-xl">
          {results.length === 0 && <li className="px-4 py-3 text-sm text-muted">{t("wh.picker.none")}</li>}
          {results.map((v) => (
            <li key={v.id}>
              <button type="button" onClick={() => choose(v)} className="block w-full px-4 py-2.5 text-left hover:bg-brand-50">
                <span className="block font-medium">{v.name}</span>
                <span className="block text-xs text-muted">
                  {[v.sku, v.barcode].filter(Boolean).join(" · ")} · {t("wh.picker.available", { qty: formatQty(v.available) })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
