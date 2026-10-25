// SEO витрины: что закрыть от поисковиков, канонические адреса, robots.txt, sitemap.xml, разметка schema.org.
import { LANGS, localizePath, type Lang } from "~/i18n";
import type { SiteSettings } from "~/lib/types";

/** Служебные страницы (пути без языкового префикса): кабинеты, корзина, вход, оформление */
const PRIVATE: RegExp[] = [
  /^\/seller(\/|$)/,
  /^\/account(\/|$)/,
  /^\/cart$/,
  /^\/checkout$/,
  /^\/order\//,
  /^\/wishlist$/,
  /^\/login$/,
  /^\/register$/,
  /^\/logout$/,
  /^\/reset-password(\/|$)/,
  /^\/confirm-email\//,
  /^\/callback$/,
  /^\/np\//,
];

export function isPrivatePath(base: string): boolean {
  return PRIVATE.some((re) => re.test(base));
}

/**
 * Параметры, с которыми страница для поиска — отдельная (категория, номер страницы).
 * Сортировка, фильтр цены, выбранный вариант товара — та же страница: canonical без них.
 */
const INDEXED_PARAMS: Record<string, string[]> = { "/catalog": ["category", "page"] };

export function canonicalSearch(base: string, search: string): string {
  const source = new URLSearchParams(search);
  const kept = new URLSearchParams();
  for (const key of INDEXED_PARAMS[base] ?? []) {
    const value = source.get(key);
    if (value && !(key === "page" && value === "1")) kept.set(key, value);
  }
  const query = kept.toString();
  return query ? `?${query}` : "";
}

/** Значение meta robots или null (индексировать). siteNoindex — тестовый сервер (SEO_NOINDEX=true). */
export function robotsFor(base: string, search: string, siteNoindex = false): string | null {
  if (siteNoindex || isPrivatePath(base)) return "noindex, nofollow";
  if (base === "/catalog" && new URLSearchParams(search).get("search")) return "noindex, follow"; // поиск по сайту
  return null;
}

/** Пути для Disallow: служебные страницы обеих языковых версий, API и админка */
const DISALLOW = [
  "/seller",
  "/account",
  "/cart",
  "/checkout",
  "/order/",
  "/wishlist",
  "/login",
  "/register",
  "/logout",
  "/reset-password",
  "/confirm-email/",
  "/callback",
  "/np/",
];

export function robotsTxt(origin: string, siteNoindex = false): string {
  if (siteNoindex) return "User-agent: *\nDisallow: /\n";
  return [
    "User-agent: *",
    ...DISALLOW.flatMap((p) => [`Disallow: ${p}`, `Disallow: /ru${p}`]),
    "Disallow: /api/",
    "Disallow: /admin/",
    "Disallow: /*?*search=",
    "Disallow: /*?*ordering=",
    "",
    `Sitemap: ${origin}/sitemap.xml`,
    "",
  ].join("\n");
}

export interface SitemapData {
  products: { slug: string; updated: string; image: string | null }[];
  categories: { slug: string; updated: string }[];
}

interface SitemapUrl {
  path: string; // без языкового префикса
  updated?: string;
  image?: string | null;
}

const STATIC_PAGES = ["/", "/catalog", "/delivery", "/contacts"];

function xml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function absolute(origin: string, url: string): string {
  return /^https?:\/\//.test(url) ? url : `${origin}${url}`;
}

/** sitemap.xml: каждая страница в двух языковых версиях с взаимными hreflang и фото товара */
export function buildSitemap(data: SitemapData, origin: string): string {
  const urls: SitemapUrl[] = [
    ...STATIC_PAGES.map((path) => ({ path })),
    ...data.categories.map((c) => ({
      path: `/catalog?category=${encodeURIComponent(c.slug)}`,
      updated: c.updated,
    })),
    ...data.products.map((p) => ({
      path: `/product/${encodeURIComponent(p.slug)}`,
      updated: p.updated,
      image: p.image,
    })),
  ];
  const href = (lang: Lang, path: string) => xml(`${origin}${localizePath(lang, path)}`);
  const entries = urls.flatMap((u) =>
    LANGS.map((lang) =>
      [
        "<url>",
        `<loc>${href(lang, u.path)}</loc>`,
        u.updated ? `<lastmod>${xml(u.updated)}</lastmod>` : "",
        ...LANGS.map((l) => `<xhtml:link rel="alternate" hreflang="${l}" href="${href(l, u.path)}"/>`),
        `<xhtml:link rel="alternate" hreflang="x-default" href="${href("uk", u.path)}"/>`,
        u.image ? `<image:image><image:loc>${xml(absolute(origin, u.image))}</image:loc></image:image>` : "",
        "</url>",
      ].join(""),
    ),
  );
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ...entries,
    "</urlset>",
    "",
  ].join("\n");
}

/** Хлебные крошки для разметки BreadcrumbList */
export function breadcrumbJsonLd(items: { name: string; url: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

/**
 * Магазин для Google: сайт + организация. С адресом самовывоза — Store (как в Google Business Profile:
 * название, адрес и телефон должны совпадать), без него — OnlineStore.
 */
export function shopJsonLd({
  origin,
  name,
  settings,
}: {
  origin: string;
  name: string;
  settings: SiteSettings | null;
}) {
  const sameAs = [settings?.google_business_url, settings?.telegram, settings?.whatsapp].filter(Boolean);
  return {
    "@context": "https://schema.org",
    "@graph": [
      { "@type": "WebSite", "@id": `${origin}/#website`, url: `${origin}/`, name, inLanguage: ["uk", "ru"] },
      {
        "@type": settings?.pickup_address ? "Store" : "OnlineStore",
        "@id": `${origin}/#shop`,
        name,
        url: `${origin}/`,
        telephone: settings?.phone || undefined,
        email: settings?.email || undefined,
        address: settings?.pickup_address
          ? { "@type": "PostalAddress", streetAddress: settings.pickup_address, addressCountry: "UA" }
          : undefined,
        sameAs: sameAs.length ? sameAs : undefined,
      },
    ],
  };
}

/** Текст для meta description: без HTML-тегов и лишних пробелов, не длиннее limit символов */
export function plainText(html: string | null | undefined, limit = 160): string {
  const text = (html ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trimEnd()}…` : text;
}
