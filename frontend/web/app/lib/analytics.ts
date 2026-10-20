/**
 * События электронной коммерции для GA4 / Google Tag Manager, Meta Pixel и TikTok Pixel.
 * Скрипты подключает <Analytics> по ID из настроек магазина; здесь — только отправка событий.
 */

export interface TrackItem {
  id: string | number;
  name: string;
  price: number;
  quantity?: number;
}

type EventName = "view_item" | "add_to_cart" | "begin_checkout" | "purchase";

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
    fbq?: (...args: unknown[]) => void;
    ttq?: { track: (...args: unknown[]) => void; page: () => void };
  }
}

const META: Record<EventName, string> = {
  view_item: "ViewContent",
  add_to_cart: "AddToCart",
  begin_checkout: "InitiateCheckout",
  purchase: "Purchase",
};
const TIKTOK: Record<EventName, string> = {
  view_item: "ViewContent",
  add_to_cart: "AddToCart",
  begin_checkout: "InitiateCheckout",
  purchase: "CompletePayment",
};

/** Строгий формат ID — они вставляются в <script> (сервер проверяет так же) */
export const PIXEL_ID = {
  ga4: /^G-[A-Z0-9]{4,15}$/,
  gtm: /^GTM-[A-Z0-9]{4,12}$/,
  meta: /^\d{5,20}$/,
  tiktok: /^[A-Z0-9]{10,30}$/,
};

export function trackEvent(
  event: EventName,
  data: { items: TrackItem[]; value?: number; orderId?: string | number },
) {
  if (typeof window === "undefined") return;
  const currency = "UAH";
  const value = data.value ?? data.items.reduce((sum, i) => sum + i.price * (i.quantity ?? 1), 0);
  const items = data.items.map((i) => ({
    item_id: String(i.id),
    item_name: i.name,
    price: i.price,
    quantity: i.quantity ?? 1,
  }));
  const ga = { currency, value, items, ...(data.orderId ? { transaction_id: String(data.orderId) } : {}) };
  if (window.gtag) window.gtag("event", event, ga);
  else if (window.dataLayer) {
    window.dataLayer.push({ ecommerce: null });
    window.dataLayer.push({ event, ecommerce: ga });
  }
  const ids = data.items.map((i) => String(i.id));
  window.fbq?.("track", META[event], { content_ids: ids, content_type: "product", value, currency });
  window.ttq?.track(TIKTOK[event], {
    contents: data.items.map((i) => ({
      content_id: String(i.id),
      content_name: i.name,
      price: i.price,
      quantity: i.quantity ?? 1,
    })),
    content_type: "product",
    value,
    currency,
  });
}

/** Переход между страницами без перезагрузки (первый просмотр отправляют сами скрипты) */
export function trackPageView(path: string) {
  if (typeof window === "undefined") return;
  window.gtag?.("event", "page_view", { page_path: path });
  window.fbq?.("track", "PageView");
  window.ttq?.page();
}
