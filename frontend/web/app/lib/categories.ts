import type { SearchOption } from "~/components/SearchSelect";

import type { Category } from "./types";

/** Категории для поиска-выбора: с отступом по дереву и числом товаров, если оно известно */
export function categoryOptions(categories: Category[], counts?: Map<number, number>): SearchOption[] {
  return categories
    .filter((c) => !counts || counts.has(c.id))
    .map((c) => ({
      value: String(c.id),
      label: c.name,
      indent: c.depth ?? 0,
      hint: counts?.has(c.id) ? String(counts.get(c.id)) : undefined,
    }));
}
