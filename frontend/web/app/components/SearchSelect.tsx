import { X } from "lucide-react";
import { useMemo, useState } from "react";

import { useT } from "~/i18n/react";

import { Input } from "./ui";

export interface SearchOption {
  value: string;
  label: string;
  /** серым после названия — например, число товаров */
  hint?: string;
  /** отступ для дерева категорий */
  indent?: number;
}

/** Слова запроса в любом порядке: «кух зміш» найдёт «Змішувачі для кухні». */
export function filterOptions(options: SearchOption[], query: string): SearchOption[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return options;
  return options.filter((o) => words.every((w) => o.label.toLowerCase().includes(w)));
}

/**
 * Выпадающий список с поиском (как автодополнение в админке Django): печатаете — список сужается.
 * Выбранное значение уходит в форму скрытым полем `name`.
 */
export function SearchSelect({
  id,
  name,
  options,
  defaultValue = "",
  placeholder,
  ariaLabel,
  className = "",
  onChange,
}: {
  /** id поля — чтобы подпись <Field> была привязана к нему */
  id?: string;
  name: string;
  options: SearchOption[];
  defaultValue?: string;
  placeholder?: string;
  ariaLabel?: string;
  className?: string;
  onChange?: (value: string) => void;
}) {
  const t = useT();
  const [value, setValue] = useState(defaultValue);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);
  const shown = useMemo(() => filterOptions(options, query).slice(0, 60), [options, query]);

  const choose = (option?: SearchOption) => {
    setValue(option?.value ?? "");
    setQuery("");
    setOpen(false);
    onChange?.(option?.value ?? "");
  };

  return (
    <div className={`relative ${className}`}>
      <input type="hidden" name={name} value={value} />
      <Input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-label={ariaLabel}
        autoComplete="off"
        value={open ? query : (selected?.label ?? "")}
        placeholder={selected?.label ?? placeholder}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && open) {
            e.preventDefault();
            if (shown[0]) choose(shown[0]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        className="w-full py-2 pr-8"
      />
      {value && (
        <button
          type="button"
          aria-label={t("ui.clear")}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => choose(undefined)}
          className="absolute top-1/2 right-2 -translate-y-1/2 text-muted hover:text-ink"
        >
          <X className="size-4" aria-hidden />
        </button>
      )}
      {open && (
        <ul
          role="listbox"
          className="absolute z-30 mt-1 max-h-72 w-full min-w-56 overflow-auto rounded-xl border border-line bg-white py-1 shadow-xl"
        >
          {shown.length === 0 && <li className="px-3 py-2 text-sm text-muted">{t("ui.noMatches")}</li>}
          {shown.map((o) => (
            <li
              key={o.value}
              role="option"
              aria-selected={o.value === value}
              onMouseDown={(e) => {
                e.preventDefault(); // не терять фокус до выбора
                choose(o);
              }}
              style={{ paddingLeft: `${0.75 + (o.indent ?? 0) * 0.75}rem` }}
              className={`cursor-pointer py-1.5 pr-3 text-sm hover:bg-brand-50 ${o.value === value ? "font-semibold" : ""}`}
            >
              {o.label}
              {o.hint && <span className="ml-1.5 text-muted">{o.hint}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
