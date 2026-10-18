import { data, Outlet, redirect } from "react-router";

import type { Route } from "./+types/lang-layout";

/** Сегмент языка: нет (украинский), "ru" — русский; /uk/... → без префикса; иное — 404 */
export function loader({ params, request }: Route.LoaderArgs) {
  if (params.lang === undefined || params.lang === "ru") return null;
  if (params.lang === "uk") {
    const url = new URL(request.url);
    throw redirect(url.pathname.replace(/^\/uk/, "") + url.search || "/", 301);
  }
  throw data("Not Found", { status: 404 });
}

export default function LangLayout() {
  return <Outlet />;
}
