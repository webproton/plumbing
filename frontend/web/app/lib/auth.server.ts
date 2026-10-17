import { redirect, type RouterContextProvider } from "react-router";

import { sessionContext } from "./session.server";

/** Требует входа: иначе — на /login с возвратом на текущую страницу */
export function requireUser(request: Request, context: Readonly<RouterContextProvider>) {
  const session = context.get(sessionContext);
  const user = session.get("user");
  if (!user || !session.has("access")) {
    const url = new URL(request.url);
    throw redirect(`/login?next=${encodeURIComponent(url.pathname + url.search)}`);
  }
  return user;
}

/** Безопасный адрес возврата после входа (только внутренние пути) */
export function safeNext(value: FormDataEntryValue | string | null, fallback = "/"): string {
  const next = typeof value === "string" ? value : "";
  return next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}
