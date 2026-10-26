// Витрина клиента во фронтенде: категории для меню, фирменный цвет, подзаголовок
import type { CSSProperties } from "react";

import type { Lang } from "~/i18n";

import type { Category, Storefront } from "./types";

/** Категории в порядке дерева (направление → раздел → категория) — для выпадающего списка каталога */
export function treeOrder(categories: Category[]): Category[] {
  const children = new Map<string | null, Category[]>();
  for (const c of categories) {
    const parent = categories.some((p) => p.slug === c.parent) ? (c.parent ?? null) : null;
    children.set(parent, [...(children.get(parent) ?? []), c]);
  }
  const ordered: Category[] = [];
  const walk = (parent: string | null) => {
    for (const c of children.get(parent) ?? []) {
      ordered.push(c);
      walk(c.slug);
    }
  };
  walk(null);
  return ordered;
}

/**
 * Категории для меню и плиток главной: у витрины одного направления (велосипеды) — его разделы
 * («Велосипеди», «Запчастини», «Екіпірування»), иначе — верхний уровень.
 */
export function navCategories(categories: Category[], storefront: Storefront | null): Category[] {
  const level = storefront?.verticals.length === 1 ? 1 : 0;
  const nav = categories.filter((c) => (c.depth ?? 0) === level);
  return nav.length ? nav : categories.filter((c) => (c.depth ?? 0) === 0);
}

/** Фирменный цвет витрины: переопределяет оттенки brand-* (Tailwind берёт их из CSS-переменных) */
export function brandStyle(color: string | undefined): CSSProperties | undefined {
  if (!color) return undefined;
  return {
    "--color-brand-50": `color-mix(in oklab, ${color} 7%, white)`,
    "--color-brand-100": `color-mix(in oklab, ${color} 16%, white)`,
    "--color-brand-500": `color-mix(in oklab, ${color} 85%, white)`,
    "--color-brand-600": color,
    "--color-brand-700": `color-mix(in oklab, ${color} 82%, black)`,
  } as CSSProperties;
}

export function storefrontTagline(storefront: Storefront | null, lang: Lang): string {
  if (!storefront) return "";
  return (lang === "ru" && storefront.tagline_ru) || storefront.tagline;
}
