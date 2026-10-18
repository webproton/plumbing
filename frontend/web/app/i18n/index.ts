import { ru } from "./ru";
import { uk, type Dict } from "./uk";

export type Lang = "uk" | "ru";
export const LANGS: Lang[] = ["uk", "ru"];
export const DEFAULT_LANG: Lang = "uk";
export const LANG_LABEL: Record<Lang, string> = { uk: "UA", ru: "RU" };
/** локаль для Intl и Accept-Language */
export const LOCALE: Record<Lang, string> = { uk: "uk-UA", ru: "ru-UA" };

const dictionaries: Record<Lang, Dict> = { uk, ru };

export type TKey = keyof Dict;
export type TFunction = (key: TKey, vars?: Record<string, string | number>) => string;

export function makeT(lang: Lang): TFunction {
  const dict = dictionaries[lang];
  return (key, vars) => {
    let text: string = dict[key] ?? uk[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
    return text;
  };
}

/** Язык по адресу: /ru/... — русский, остальное — украинский (по умолчанию) */
export function langFromPath(pathname: string): Lang {
  return pathname === "/ru" || pathname.startsWith("/ru/") ? "ru" : DEFAULT_LANG;
}

export function langFromRequest(request: Request): Lang {
  return langFromPath(new URL(request.url).pathname);
}

/** Путь без языкового префикса: /ru/catalog → /catalog */
export function stripLang(pathname: string): string {
  if (pathname === "/ru") return "/";
  return pathname.startsWith("/ru/") ? pathname.slice(3) : pathname;
}

/** Добавить префикс языка к внутреннему пути: ("ru", "/catalog?x=1") → "/ru/catalog?x=1" */
export function localizePath(lang: Lang, to: string): string {
  if (lang === DEFAULT_LANG || !to.startsWith("/") || to.startsWith("//")) return to;
  if (to === "/") return "/ru";
  return to.startsWith("/ru/") || to === "/ru" ? to : `/ru${to}`;
}

/** t() для meta-функций: язык берётся из данных корневого маршрута */
export function tFromMatches(matches: readonly ({ loaderData?: unknown } | undefined)[]): TFunction {
  const lang = (matches[0]?.loaderData as { lang?: Lang } | undefined)?.lang ?? DEFAULT_LANG;
  return makeT(lang);
}
