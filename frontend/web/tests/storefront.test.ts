import { describe, expect, it } from "vitest";

import { brandStyle, navCategories, storefrontTagline, treeOrder } from "~/lib/storefront";
import type { Category, Storefront } from "~/lib/types";

const cat = (slug: string, depth: number, parent: string | null = null): Category => ({
  id: slug.length,
  slug,
  name: slug,
  photo: null,
  product_list: "",
  parent,
  depth,
  vertical: "bikes",
});

const categories = [
  cat("zapchastyny", 1, "velo"),
  cat("velo", 0),
  cat("lantsiugy", 2, "zapchastyny"),
  cat("instrument", 0),
  cat("velosypedy", 1, "velo"),
];

const store = (verticals: string[]): Storefront => ({
  slug: "velo",
  name: "Вело",
  tagline: "Велосипеди",
  tagline_ru: "Велосипеды",
  verticals,
  brand_color: "#15803d",
  logo: null,
  phone: "",
  email: "",
  address: "",
  telegram_bot: "",
  is_demo: true,
});

describe("storefront", () => {
  it("orders categories as a tree", () => {
    expect(treeOrder(categories).map((c) => c.slug)).toEqual([
      "velo",
      "zapchastyny",
      "lantsiugy",
      "velosypedy",
      "instrument",
    ]);
  });

  it("menu shows sections for a one-topic storefront, top level otherwise", () => {
    expect(navCategories(categories, store(["bikes"])).map((c) => c.slug)).toEqual([
      "zapchastyny",
      "velosypedy",
    ]);
    expect(navCategories(categories, null).map((c) => c.slug)).toEqual(["velo", "instrument"]);
    expect(navCategories(categories, store(["bikes", "tools"])).map((c) => c.slug)).toEqual([
      "velo",
      "instrument",
    ]);
  });

  it("brand color and tagline", () => {
    expect(brandStyle("")).toBeUndefined();
    expect(brandStyle("#15803d")).toMatchObject({ "--color-brand-600": "#15803d" });
    expect(storefrontTagline(store(["bikes"]), "ru")).toBe("Велосипеды");
    expect(storefrontTagline(null, "uk")).toBe("");
  });
});
