import { apiContext } from "~/lib/context.server";
import type { NpWarehouse } from "~/lib/types";

import type { Route } from "./+types/warehouses";

/** Ресурсный маршрут: отделения и поштоматы города (?city=Ref&q=номер или улица) */
export async function loader({ request, context }: Route.LoaderArgs) {
  const params = new URL(request.url).searchParams;
  const city = params.get("city") ?? "";
  if (city.length !== 36) return Response.json([]);
  const list = await context
    .get(apiContext)
    .get<NpWarehouse[]>("/delivery/np/warehouses/", { query: { city, q: params.get("q") ?? "" } })
    .catch(() => []);
  return Response.json(list);
}
