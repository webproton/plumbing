import { apiContext } from "~/lib/context.server";
import type { NpCity } from "~/lib/types";

import type { Route } from "./+types/cities";

/** Ресурсный маршрут: поиск населённых пунктов Новой Почты (?q=) */
export async function loader({ request, context }: Route.LoaderArgs) {
  const q = new URL(request.url).searchParams.get("q") ?? "";
  if (q.trim().length < 2) return Response.json([]);
  const cities = await context
    .get(apiContext)
    .get<NpCity[]>("/delivery/np/cities/", { query: { q } })
    .catch(() => []);
  return Response.json(cities);
}
