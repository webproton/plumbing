import { apiContext } from "~/lib/context.server";
import type { NpEstimate } from "~/lib/types";

import type { Route } from "./+types/estimate";

/** Ресурсный маршрут: стоимость и дата доставки до города (?city=Ref&cost=сумма) */
export async function loader({ request, context }: Route.LoaderArgs) {
  const params = new URL(request.url).searchParams;
  const city = params.get("city") ?? "";
  if (city.length !== 36) return Response.json({});
  const estimate = await context
    .get(apiContext)
    .get<NpEstimate>("/delivery/np/estimate/", { query: { city, cost: params.get("cost") ?? "" } })
    .catch(() => ({}));
  return Response.json(estimate);
}
