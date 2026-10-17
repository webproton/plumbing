import { redirect } from "react-router";

import type { Route } from "./+types/product";

/** Старый SPA: /products/:slug[/variant/:variant] → /product/:slug */
export function loader({ params }: Route.LoaderArgs) {
  return redirect(`/product/${params.slug}`, 301);
}
