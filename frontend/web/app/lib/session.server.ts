import { createCookieSessionStorage, createContext, type Session } from "react-router";

import { config } from "./config.server";

/**
 * Сессия в подписанной HttpOnly-cookie. Токены Django не доступны JavaScript в браузере —
 * все запросы к API с авторизацией идут через сервер фронтенда (loaders/actions).
 */
export interface SessionData {
  access: string;
  refresh: string;
  cartUuid: string;
  user: { email: string; name: string; staff?: boolean };
}

export interface FlashData {
  notice: string;
  /** заказ для события «покупка» в аналитике (страница «Заказ принят») */
  purchase: { id: number; value: number; items: { id: number; name: string; price: number; quantity: number }[] };
}

export type AppSession = Session<SessionData, FlashData>;

export const sessionStorage = createCookieSessionStorage<SessionData, FlashData>({
  cookie: {
    name: "__session",
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: config.secureCookies,
    secrets: [config.sessionSecret],
    maxAge: 60 * 60 * 24 * 30,
  },
});

/** Сессия текущего запроса (кладёт корневой middleware) */
export const sessionContext = createContext<AppSession>();
