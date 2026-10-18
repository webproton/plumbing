import { Package } from "lucide-react";

import { Badge, ButtonLink, EmptyState, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { Link, useLang, useT } from "~/i18n/react";
import { requireUser } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import { formatDate, formatPrice, statusTone } from "~/lib/format";
import type { OrderListItem } from "~/lib/types";

import type { Route } from "./+types/orders";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("account.orders") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  requireUser(request, context);
  return { orders: await context.get(apiContext).get<OrderListItem[]>("/orders/history/") };
}

export default function Orders({ loaderData }: Route.ComponentProps) {
  const t = useT();
  const lang = useLang();
  if (!loaderData.orders.length) {
    return (
      <EmptyState icon={Package} title={t("account.noOrders.title")}>
        <p className="mb-4">{t("account.noOrders.text")}</p>
        <ButtonLink to="/catalog">{t("common.toCatalog")}</ButtonLink>
      </EmptyState>
    );
  }
  return (
    <div>
      <PageTitle>{t("account.orders")}</PageTitle>
      <ul className="space-y-3">
        {loaderData.orders.map((o) => (
          <li key={o.id}>
            <Link to={`/account/orders/${o.id}`} className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-white p-4 hover:border-brand-500">
              <div className="flex -space-x-3">
                {o.list_of_product_images.slice(0, 3).map((img) => (
                  <img key={img.variant_id} src={img.photo} alt="" className="size-12 rounded-lg border-2 border-white bg-surface object-contain" />
                ))}
              </div>
              <div className="flex-1">
                <p className="font-semibold">{t("account.order", { id: o.id })}</p>
                <p className="text-sm text-muted">{formatDate(o.creation_date, lang)}</p>
              </div>
              <Badge tone={statusTone(o.status_order)}>{o.status_order_display}</Badge>
              <span className="font-semibold">{formatPrice(o.total_price)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
