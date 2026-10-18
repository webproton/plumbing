import { data, type RouterContextProvider } from "react-router";

import { requireUser } from "./auth.server";
import { apiContext } from "./context.server";
import type { Paginated, WarehouseMe } from "./types";

export const PAGE_SIZE = 25;

/** Для loaders/actions кабинета: вход обязателен, роль «склад» проверяет сервер при каждом запросе API. */
export function requireSeller(request: Request, context: Readonly<RouterContextProvider>) {
  requireUser(request, context);
  return context.get(apiContext);
}

export function pageOf(request: Request): number {
  return Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
}

export function pagesOf<T>(page: Paginated<T>, size = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(page.count / size));
}

/** Список с пагинацией; несуществующая страница → пустой результат, а не ошибка */
export async function paged<T>(promise: Promise<Paginated<T>>): Promise<Paginated<T>> {
  try {
    return await promise;
  } catch (e) {
    if ((e as { status?: number }).status === 404) return { count: 0, next: null, previous: null, results: [] };
    throw e;
  }
}

export function bad(errors: Record<string, string>, values?: Record<string, string>) {
  return data({ ok: false as const, errors, values }, { status: 400 });
}

export type WarehouseMeData = WarehouseMe;
