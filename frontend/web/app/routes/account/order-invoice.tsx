import { requireUser } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";

import type { Route } from "./+types/order-invoice";

/** Ресурсный маршрут: счёт на оплату своего заказа (PDF) */
export async function loader({ request, params, context }: Route.LoaderArgs) {
  requireUser(request, context);
  const upstream = await context.get(apiContext).download(`/orders/history/${params.id}/invoice/`);
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `inline; filename="invoice-${params.id}.pdf"`,
      "Cache-Control": "private, no-store",
    },
  });
}
