import { describe, expect, it } from "vitest";

import { thumb } from "~/lib/thumb";

describe("thumb", () => {
  it("строит адрес уменьшенной копии из адреса фото", () => {
    expect(thumb("https://shop.example.com/media/products/a-1.png", 400)).toBe(
      "https://shop.example.com/media/thumbs/400/products/a-1.png.webp",
    );
    expect(thumb("/media/products_new/b.jpg?v=2", 160)).toBe("/media/thumbs/160/products_new/b.jpg.webp");
  });

  it("чужие ссылки и пустые — как есть", () => {
    expect(thumb("https://cdn.supplier.ua/p.jpg", 400)).toBe("https://cdn.supplier.ua/p.jpg");
    expect(thumb("/media/thumbs/400/products/a.png.webp", 160)).toBe("/media/thumbs/400/products/a.png.webp");
    expect(thumb(null, 400)).toBeUndefined();
  });
});
