import { localRedirect } from "~/i18n/server";

import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";

import type { Route } from "./+types/logout";

export async function action({ request, context }: Route.ActionArgs) {
  const api = context.get(apiContext);
  const session = context.get(sessionContext);
  const refresh = session.get("refresh");
  // отзываем refresh-токен на сервере (blacklist), ошибки не мешают выходу
  if (refresh) await api.post("/dj-rest-auth/logout/", { refresh }).catch(() => undefined);
  api.signOut();
  session.unset("cartUuid");
  return localRedirect(request, "/");
}

export function loader({ request }: Route.LoaderArgs) {
  return localRedirect(request, "/");
}
