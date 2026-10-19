import { useT } from "~/i18n/react";
import type { ManageVariant } from "~/lib/types";

import { Field, Input } from "../ui";

/** «5999.0000» → «5999», пусто → "" */
export function plain(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  return Number.isFinite(n) ? String(n) : value;
}

/** Поля варианта товара (общие для создания и редактирования). Ошибки — по именам полей API. */
export function VariantFields({
  variant,
  brands,
  errors = {},
  withName = true,
  listId = "brands",
}: {
  variant?: ManageVariant;
  brands: string[];
  errors?: Record<string, string>;
  withName?: boolean;
  listId?: string;
}) {
  const t = useT();
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {withName && (
        <Field
          label={t("prod.field.variantName")}
          hint={t("prod.field.variantNameHint")}
          error={errors.variant_name}
        >
          {(p) => (
            <Input {...p} name="variant_name" defaultValue={variant?.variant_name ?? ""} maxLength={255} />
          )}
        </Field>
      )}
      <Field
        label={t("prod.field.sku")}
        hint={variant ? undefined : t("prod.field.skuHint")}
        error={errors.code}
      >
        {(p) => <Input {...p} name="code" defaultValue={variant?.code ?? ""} maxLength={50} />}
      </Field>
      <Field
        label={t("prod.field.barcode")}
        hint={variant ? undefined : t("prod.field.barcodeHint")}
        error={errors.barcode}
      >
        {(p) => (
          <Input
            {...p}
            name="barcode"
            defaultValue={variant?.barcode ?? ""}
            maxLength={50}
            inputMode="numeric"
          />
        )}
      </Field>
      <Field label={t("prod.field.price")} error={errors.price}>
        {(p) => (
          <Input
            {...p}
            name="price"
            type="number"
            min="0.01"
            step="0.01"
            required
            defaultValue={plain(variant?.price)}
          />
        )}
      </Field>
      <Field label={t("prod.field.oldPrice")} hint={t("prod.field.oldPriceHint")} error={errors.old_price}>
        {(p) => (
          <Input
            {...p}
            name="old_price"
            type="number"
            min="0"
            step="0.01"
            defaultValue={plain(variant?.original_price_value)}
          />
        )}
      </Field>
      <Field label={t("prod.field.cost")} error={errors.cost_price}>
        {(p) => (
          <Input
            {...p}
            name="cost_price"
            type="number"
            min="0"
            step="0.01"
            defaultValue={plain(variant?.cost_price)}
          />
        )}
      </Field>
      <Field label={t("prod.field.brand")} error={errors.brand_name}>
        {(p) => (
          <Input {...p} name="brand_name" list={listId} defaultValue={variant?.brand ?? ""} maxLength={255} />
        )}
      </Field>
      <datalist id={listId}>
        {brands.map((b) => (
          <option key={b} value={b} />
        ))}
      </datalist>
      <label className="flex items-center gap-2 self-end pb-3 text-sm">
        <input
          type="checkbox"
          name="available"
          value="1"
          defaultChecked={variant?.available ?? false}
          className="accent-brand-600 size-4"
        />
        {t("prod.field.visible")}
      </label>
    </div>
  );
}

/** Значения формы варианта → тело запроса API */
export function variantPayload(form: FormData, withName = true): Record<string, unknown> {
  const v = (k: string) => String(form.get(k) ?? "").trim();
  const num = (k: string) => (v(k) === "" ? null : v(k));
  return {
    ...(withName ? { variant_name: v("variant_name") || null } : {}),
    code: v("code") || null,
    barcode: v("barcode") || null,
    price: v("price"),
    old_price: num("old_price"),
    cost_price: num("cost_price"),
    brand_name: v("brand_name"),
    available: form.get("available") === "1",
  };
}
