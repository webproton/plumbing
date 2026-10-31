/**
 * Уменьшенная копия фото из /media/ — WebP нужной ширины (сервер делает её при первом показе и кладёт рядом).
 * Для списков и каталога: оригиналы по 300–700 КБ грузятся долго. Чужие ссылки (CDN поставщика) — как есть.
 */
export type ThumbWidth = 160 | 400 | 800;

export function thumb(url: string | null | undefined, width: ThumbWidth): string | undefined {
  if (!url) return undefined;
  const at = url.indexOf("/media/");
  if (at < 0 || url.includes("/media/thumbs/")) return url;
  const rest = url.slice(at + "/media/".length).split(/[?#]/)[0];
  return `${url.slice(0, at)}/media/thumbs/${width}/${rest}.webp`;
}
