import { localRedirect } from "~/i18n/server";

import type { Route } from "./+types/category";

export function loader({ request }: Route.LoaderArgs) {
  return localRedirect(request, "/catalog", 301);
}
