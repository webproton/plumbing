import { describe, expect, it } from "vitest";

import { langFromPath, localizePath, makeT, stripLang } from "~/i18n";
import { ru } from "~/i18n/ru";
import { uk } from "~/i18n/uk";

describe("i18n paths", () => {
  it("detects language from URL", () => {
    expect(langFromPath("/")).toBe("uk");
    expect(langFromPath("/catalog")).toBe("uk");
    expect(langFromPath("/ru")).toBe("ru");
    expect(langFromPath("/ru/product/x")).toBe("ru");
    expect(langFromPath("/rus")).toBe("uk");
  });

  it("adds and strips the prefix", () => {
    expect(localizePath("ru", "/")).toBe("/ru");
    expect(localizePath("ru", "/catalog?x=1")).toBe("/ru/catalog?x=1");
    expect(localizePath("ru", "/ru/catalog")).toBe("/ru/catalog");
    expect(localizePath("uk", "/catalog")).toBe("/catalog");
    expect(localizePath("ru", "https://example.com")).toBe("https://example.com");
    expect(stripLang("/ru/catalog")).toBe("/catalog");
    expect(stripLang("/ru")).toBe("/");
  });
});

describe("dictionaries", () => {
  it("ru has every uk key and no empty values", () => {
    expect(Object.keys(ru).sort()).toEqual(Object.keys(uk).sort());
    for (const [key, value] of Object.entries(ru)) expect(value, key).not.toBe("");
  });

  it("interpolates variables", () => {
    expect(makeT("uk")("nav.cart", { count: 3 })).toBe("Кошик, товарів: 3");
    expect(makeT("ru")("checkout.submit", { total: "100 ₴" })).toBe("Подтвердить заказ на 100 ₴");
  });
});
