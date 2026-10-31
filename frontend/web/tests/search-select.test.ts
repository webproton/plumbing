import { describe, expect, it } from "vitest";

import { filterOptions } from "~/components/SearchSelect";
import { categoryOptions } from "~/lib/categories";

describe("поиск в выпадающем списке", () => {
  const options = [
    { value: "1", label: "Змішувачі для кухні" },
    { value: "2", label: "Змішувачі для ванни" },
    { value: "3", label: "Труби та фітинги" },
  ];

  it("слова в любом порядке и без учёта регистра", () => {
    expect(filterOptions(options, "кух зміш").map((o) => o.value)).toEqual(["1"]);
    expect(filterOptions(options, "ЗМІШ").map((o) => o.value)).toEqual(["1", "2"]);
    expect(filterOptions(options, "  ")).toHaveLength(3);
    expect(filterOptions(options, "насос")).toEqual([]);
  });

  it("категории: отступ по дереву, число товаров, только где есть товары", () => {
    const categories = [
      { id: 1, slug: "a", name: "Змішувачі", photo: null, product_list: "", depth: 1 },
      { id: 2, slug: "b", name: "Для кухні", photo: null, product_list: "", depth: 2 },
      { id: 3, slug: "c", name: "Порожня", photo: null, product_list: "", depth: 2 },
    ];
    expect(categoryOptions(categories, new Map([[1, 5], [2, 3]]))).toEqual([
      { value: "1", label: "Змішувачі", indent: 1, hint: "5" },
      { value: "2", label: "Для кухні", indent: 2, hint: "3" },
    ]);
    expect(categoryOptions(categories)).toHaveLength(3);
  });
});
