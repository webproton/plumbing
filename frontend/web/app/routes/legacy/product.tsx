import { localRedirect } from "~/i18n/server";

import type { Route } from "./+types/product";

/** Старый SPA: /products/:slug[/variant/:variant] → /product/:slug */
export function loader({ params, request }: Route.LoaderArgs) {
  return localRedirect(request, `/product/${params.slug}`, 301);
}
