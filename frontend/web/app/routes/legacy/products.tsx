import { localRedirect } from "~/i18n/server";

import type { Route } from "./+types/products";

/** Старый SPA: /products/?category=… → /catalog?category=… (301 для поисковиков) */
export function loader({ request }: Route.LoaderArgs) {
  return localRedirect(request, `/catalog${new URL(request.url).search}`, 301);
}
