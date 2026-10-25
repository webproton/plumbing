import { describe, expect, it } from "vitest";

import { buildSitemap, canonicalSearch, plainText, robotsFor, robotsTxt, shopJsonLd } from "~/lib/seo";

describe("canonical и noindex", () => {
  it("каталог: в canonical только категория и страница (не первая)", () => {
    expect(canonicalSearch("/catalog", "?category=zmishuvachi&ordering=-price&min_price=100&page=2")).toBe(
      "?category=zmishuvachi&page=2",
    );
    expect(canonicalSearch("/catalog", "?page=1")).toBe("");
    expect(canonicalSearch("/product/kran", "?v=12")).toBe(""); // вариант товара — та же страница
  });

  it("служебные страницы и поиск по сайту закрыты, остальное открыто", () => {
    for (const path of [
      "/seller",
      "/seller/orders/5",
      "/account/orders",
      "/cart",
      "/checkout",
      "/login",
      "/order/7/success",
    ]) {
      expect(robotsFor(path, "")).toBe("noindex, nofollow");
    }
    expect(robotsFor("/catalog", "?search=кран")).toBe("noindex, follow");
    expect(robotsFor("/catalog", "?category=x")).toBeNull();
    expect(robotsFor("/product/kran", "")).toBeNull();
    expect(robotsFor("/product/kran", "", true)).toBe("noindex, nofollow"); // SEO_NOINDEX — тестовый сервер
  });
});

describe("robots.txt и sitemap.xml", () => {
  it("robots закрывает кабинеты обеих языковых версий и даёт ссылку на sitemap", () => {
    const txt = robotsTxt("https://shop.ua");
    expect(txt).toContain("Disallow: /seller\n");
    expect(txt).toContain("Disallow: /ru/seller\n");
    expect(txt).toContain("Disallow: /api/\n");
    expect(txt).toContain("Sitemap: https://shop.ua/sitemap.xml");
    expect(robotsTxt("https://test.shop.ua", true)).toBe("User-agent: *\nDisallow: /\n");
  });

  it("sitemap: каждая страница на двух языках, hreflang, фото, экранирование", () => {
    const xml = buildSitemap(
      {
        products: [{ slug: "kran-1-2", updated: "2026-10-20", image: "/media/products/k&r.jpg" }],
        categories: [{ slug: "zmishuvachi", updated: "2026-10-19" }],
      },
      "https://shop.ua",
    );
    expect(xml.match(/<url>/g)).toHaveLength((4 + 1 + 1) * 2); // страницы + категория + товар, uk и ru
    expect(xml).toContain("<loc>https://shop.ua/product/kran-1-2</loc><lastmod>2026-10-20</lastmod>");
    expect(xml).toContain("<loc>https://shop.ua/ru/product/kran-1-2</loc>");
    expect(xml).toContain('hreflang="ru" href="https://shop.ua/ru/catalog?category=zmishuvachi"');
    expect(xml).toContain("<image:loc>https://shop.ua/media/products/k&amp;r.jpg</image:loc>");
    expect(xml).not.toContain("/seller");
  });
});

describe("разметка и тексты", () => {
  it("магазин с адресом самовывоза — Store, без адреса — OnlineStore", () => {
    const withAddress = shopJsonLd({
      origin: "https://shop.ua",
      name: "Сантехніка",
      settings: {
        phone: "+380441234567",
        email: null,
        telegram: null,
        whatsapp: null,
        pickup_address: "Київ, вул. Тестова, 1",
      },
    });
    expect(withAddress["@graph"][1]).toMatchObject({
      "@type": "Store",
      address: { streetAddress: "Київ, вул. Тестова, 1" },
    });
    const online = shopJsonLd({ origin: "https://shop.ua", name: "Сантехніка", settings: null });
    expect(online["@graph"][1]["@type"]).toBe("OnlineStore");
  });

  it("описание товара без HTML и не длиннее 160 символов", () => {
    expect(plainText("<p>Хромований &amp; надійний</p>")).toBe("Хромований & надійний");
    expect(plainText("а".repeat(300))).toHaveLength(160);
  });
});
