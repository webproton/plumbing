import { data } from "react-router";

import type { makeT } from "~/i18n";
import { ApiError, type Api } from "~/lib/api.server";

/**
 * «Створити товар» из найденной позиции поставщика (поиск в «Товарах» и поиск кабинета):
 * та же логика, что на странице поставщика. Форма: source, item.
 */
export async function publishSupplierItem(api: Api, form: FormData, t: ReturnType<typeof makeT>) {
  try {
    const r = await api.post<{
      created: number;
      linked: number;
      skipped: number;
      no_rate: Record<string, number>;
    }>(`/imports/sources/${Number(form.get("source"))}/publish/`, { ids: [Number(form.get("item"))] });
    const noRate = Object.keys(r.no_rate ?? {});
    if (r.created) return { ok: true as const, message: t("prod.suppliers.created") };
    if (r.linked) return { ok: true as const, message: t("prod.suppliers.linked") };
    const message = noRate.length
      ? t("src.noRate", { currencies: noRate.join(", ") })
      : t("prod.suppliers.noName");
    return data({ ok: false as const, message }, { status: 400 });
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, message: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
}
