import { redirect } from "react-router";

import type { Route } from "./+types/products";

/** Старый SPA: /products/?category=… → /catalog?category=… (301 для поисковиков) */
export function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  return redirect(`/catalog${url.search}`, 301);
}
