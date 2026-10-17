import type { Api } from "./api.server";
import { ApiError } from "./api.server";
import type { AppSession } from "./session.server";
import type { Cart } from "./types";

export interface CartLine {
  product: number;
  variant: number | null;
  quantity: number;
}

/** Текущая корзина (гостя — по cart_uuid из сессии, пользователя — его открытая корзина) */
export async function getCart(api: Api, session: AppSession): Promise<Cart | null> {
  const cart = await api.get<Cart | undefined>("/orders/cart/current/", {
    query: { cart_uuid: session.get("cartUuid") },
  });
  if (!cart) return null;
  if (cart.cart_uuid !== session.get("cartUuid")) session.set("cartUuid", cart.cart_uuid);
  return cart;
}

/** Сохранить корзину целиком (сервер приводит содержимое ровно к переданному списку) */
export async function saveCart(api: Api, session: AppSession, lines: CartLine[]): Promise<Cart | null> {
  const items = lines.filter((l) => l.quantity > 0);
  if (!items.length) {
    const current = await getCart(api, session);
    if (current) {
      await api.put(`/orders/cart/${current.id}/`, {
        cart_uuid: current.cart_uuid,
        cart_items: current.cart_items.map((i) => ({ product: i.product, variant: i.variant, quantity: 0 })),
      }, { query: { cart_uuid: current.cart_uuid } });
    }
    return null;
  }
  const cart = await api.post<Cart>("/orders/cart/", {
    cart_uuid: session.get("cartUuid"),
    cart_items: items,
  });
  session.set("cartUuid", cart.cart_uuid);
  return cart;
}

export function cartLines(cart: Cart | null): CartLine[] {
  return (cart?.cart_items ?? []).map((i) => ({ product: i.product, variant: i.variant, quantity: i.quantity }));
}

export function cartCount(cart: Cart | null): number {
  return (cart?.cart_items ?? []).reduce((sum, i) => sum + i.quantity, 0);
}

export function cartTotal(cart: Cart | null): number {
  return (cart?.cart_items ?? []).reduce((sum, i) => sum + Number(i.price ?? 0) * i.quantity, 0);
}

export { ApiError };
