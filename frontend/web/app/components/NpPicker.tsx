import { MapPin, Package } from "lucide-react";
import { useRef, useState } from "react";
import { useFetcher } from "react-router";

import { useLocalPath, useT } from "~/i18n/react";
import type { NpCity, NpWarehouse } from "~/lib/types";

import { Field, Input } from "./ui";

export interface NpValue {
  cityRef: string;
  cityName: string;
  warehouseRef: string;
  warehouseName: string;
  department: string;
}

/**
 * Город и отделение Новой Почты с автодополнением из справочника.
 * Без JavaScript остаются обычные поля «город» и «отделение» (их имена — names.city / names.department).
 * Выбранные из справочника Ref уходят скрытыми полями.
 */
export function NpPicker({
  names,
  initial,
  errors = {},
  onCity,
}: {
  names: { city: string; department: string; cityRef: string; warehouseRef: string; warehouseName: string };
  initial?: Partial<NpValue>;
  errors?: { city?: string; department?: string };
  onCity?: (ref: string) => void;
}) {
  const t = useT();
  const local = useLocalPath();
  const cities = useFetcher<NpCity[]>();
  const whs = useFetcher<NpWarehouse[]>();
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [cityName, setCityName] = useState(initial?.cityName ?? "");
  const [cityRef, setCityRef] = useState(initial?.cityRef ?? "");
  const [department, setDepartment] = useState(initial?.department ?? "");
  const [warehouse, setWarehouse] = useState({
    ref: initial?.warehouseRef ?? "",
    name: initial?.warehouseName ?? "",
  });
  const [open, setOpen] = useState<"city" | "warehouse" | null>(null);

  const debounce = (fn: () => void) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(fn, 250);
  };
  const searchCities = (q: string) => {
    setCityName(q);
    setCityRef("");
    setWarehouse({ ref: "", name: "" });
    onCity?.("");
    setOpen("city");
    if (q.trim().length >= 2)
      debounce(() => cities.load(local(`/np/cities?q=${encodeURIComponent(q.trim())}`)));
  };
  const chooseCity = (c: NpCity) => {
    setCityName(c.name);
    setCityRef(c.ref);
    setOpen("warehouse");
    onCity?.(c.ref);
    whs.load(local(`/np/warehouses?city=${c.ref}`));
  };
  const searchWarehouses = (q: string) => {
    setDepartment(q);
    setWarehouse({ ref: "", name: "" });
    setOpen("warehouse");
    if (cityRef)
      debounce(() => whs.load(local(`/np/warehouses?city=${cityRef}&q=${encodeURIComponent(q.trim())}`)));
  };
  const chooseWarehouse = (w: NpWarehouse) => {
    setDepartment(w.number);
    setWarehouse({ ref: w.ref, name: w.name });
    setOpen(null);
  };

  const cityList = open === "city" && cityName.trim().length >= 2 ? (cities.data ?? []) : [];
  const whList = open === "warehouse" && cityRef ? (whs.data ?? []) : [];
  const listClass =
    "absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-line bg-white shadow-xl";
  const optionClass =
    "block w-full px-4 py-2 text-left text-sm hover:bg-brand-50 focus:bg-brand-50 focus:outline-none";

  return (
    <div className="grid gap-4 sm:grid-cols-2" onKeyDown={(e) => e.key === "Escape" && setOpen(null)}>
      <input type="hidden" name={names.cityRef} value={cityRef} />
      <input type="hidden" name={names.warehouseRef} value={warehouse.ref} />
      <input type="hidden" name={names.warehouseName} value={warehouse.name} />
      <div className="relative">
        <Field label={t("checkout.city")} error={errors.city}>
          {(p) => (
            <Input
              {...p}
              name={names.city}
              value={cityName}
              onChange={(e) => searchCities(e.target.value)}
              onFocus={() => setOpen("city")}
              autoComplete="off"
              role="combobox"
              aria-expanded={cityList.length > 0}
              aria-autocomplete="list"
            />
          )}
        </Field>
        {cityList.length > 0 && (
          <ul className={listClass} role="listbox">
            {cityList.map((c) => (
              <li key={c.ref}>
                <button type="button" className={optionClass} onClick={() => chooseCity(c)}>
                  <MapPin className="text-muted mr-1.5 inline size-3.5" aria-hidden />
                  {c.label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="relative">
        <Field
          label={t("checkout.department")}
          error={errors.department}
          hint={warehouse.name || (cityRef ? t("np.searchHint") : undefined)}
        >
          {(p) => (
            <Input
              {...p}
              name={names.department}
              value={department}
              onChange={(e) => searchWarehouses(e.target.value)}
              onFocus={() => cityRef && setOpen("warehouse")}
              autoComplete="off"
              role="combobox"
              aria-expanded={whList.length > 0}
              aria-autocomplete="list"
            />
          )}
        </Field>
        {whList.length > 0 && (
          <ul className={listClass} role="listbox">
            {whList.map((w) => (
              <li key={w.ref}>
                <button type="button" className={optionClass} onClick={() => chooseWarehouse(w)}>
                  {w.kind === "postomat" ? (
                    <Package className="text-muted mr-1.5 inline size-3.5" aria-hidden />
                  ) : (
                    <MapPin className="text-muted mr-1.5 inline size-3.5" aria-hidden />
                  )}
                  {w.name}
                  {w.max_weight ? (
                    <span className="text-muted"> · {t("np.maxWeight", { kg: w.max_weight })}</span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
