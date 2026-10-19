import { describe, expect, it } from "vitest";

import { formatDateTime, formatPrice, formatQty, pluralize, statusTone } from "~/lib/format";

describe("format", () => {
  it("formats prices in UAH", () => {
    expect(formatPrice("1500.50").replace(/\s/g, " ")).toBe("1 500,5 ₴");
    expect(formatPrice(null)).toBe("—");
    expect(formatPrice("abc")).toBe("—");
  });

  it("strips trailing zeros from quantities", () => {
    expect(formatQty("2.000")).toBe("2");
    expect(formatQty("0.500")).toBe("0,5");
  });

  it("pluralizes in Russian", () => {
    const forms: [string, string, string] = ["товар", "товара", "товаров"];
    expect([1, 2, 5, 11, 21, 22, 25].map((n) => pluralize(n, forms))).toEqual([
      "товар", "товара", "товаров", "товаров", "товар", "товара", "товаров",
    ]);
  });

  it("maps order status to badge tone", () => {
    expect(statusTone("completed")).toBe("success");
    expect(statusTone("canceled")).toBe("danger");
    expect(statusTone("in_processing")).toBe("info");
  });
});

describe("formatDateTime", () => {
  it("показывает время по Киеву независимо от часового пояса сервера", () => {
    expect(formatDateTime("2026-10-19T12:08:00Z", "uk")).toBe("19.10.2026, 15:08");
    expect(formatDateTime("2026-10-19T12:08:00Z", "ru")).toBe("19.10.2026, 15:08");
  });
});
