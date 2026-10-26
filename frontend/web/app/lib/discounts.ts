/** Знижка партнера по брендах у джерелі товарів: текст форми ↔ { бренд: відсоток }. */

const BRAND_LINE = /^(.+?)[\s:=—–-]+(\d+(?:[.,]\d+)?)\s*%?$/;

/** «KOER 17,7» по рядку → { KOER: "17.7" }; незрозумілий рядок піде як є — сервер поверне помилку поля. */
export function parseBrandDiscounts(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const m = BRAND_LINE.exec(line);
    if (m) out[m[1].trim()] = m[2].replace(",", ".");
    else out[line] = "?";
  }
  return out;
}

export function brandDiscountsText(brands: Record<string, number> | undefined): string {
  return Object.entries(brands ?? {})
    .map(([brand, percent]) => `${brand} ${percent}`)
    .join("\n");
}
