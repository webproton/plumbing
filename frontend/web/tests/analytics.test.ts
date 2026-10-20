import { afterEach, describe, expect, it, vi } from "vitest";

import { PIXEL_ID, trackEvent } from "~/lib/analytics";

describe("analytics", () => {
  afterEach(() => {
    delete window.gtag;
    delete window.fbq;
    delete window.ttq;
    delete window.dataLayer;
  });

  it("отправляет событие в GA4, Meta и TikTok", () => {
    window.gtag = vi.fn();
    window.fbq = vi.fn();
    window.ttq = { track: vi.fn(), page: vi.fn() };
    trackEvent("purchase", { orderId: 7, items: [{ id: 3, name: "Змішувач", price: 1250.5, quantity: 2 }] });
    expect(window.gtag).toHaveBeenCalledWith(
      "event",
      "purchase",
      expect.objectContaining({ value: 2501, transaction_id: "7", currency: "UAH" }),
    );
    expect(window.fbq).toHaveBeenCalledWith(
      "track",
      "Purchase",
      expect.objectContaining({ content_ids: ["3"], value: 2501 }),
    );
    expect(window.ttq.track).toHaveBeenCalledWith(
      "CompletePayment",
      expect.objectContaining({ value: 2501 }),
    );
  });

  it("без gtag пишет в dataLayer (Google Tag Manager)", () => {
    window.dataLayer = [];
    trackEvent("add_to_cart", { items: [{ id: 1, name: "Сифон", price: 100 }] });
    expect(window.dataLayer).toContainEqual(expect.objectContaining({ event: "add_to_cart" }));
  });

  it("ID пикселей — только строгий формат", () => {
    expect(PIXEL_ID.ga4.test("G-ABC123XYZ")).toBe(true);
    expect(PIXEL_ID.ga4.test("G-1');alert(1);//")).toBe(false);
    expect(PIXEL_ID.meta.test("123456789012345")).toBe(true);
    expect(PIXEL_ID.meta.test("123</script>")).toBe(false);
    expect(PIXEL_ID.gtm.test("GTM-AB12CD")).toBe(true);
  });
});
