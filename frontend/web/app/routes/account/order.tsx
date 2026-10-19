import { data, Form, useNavigation } from "react-router";

import { Alert, Badge, Button, Card, PageTitle } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useLang, useLocalPath, useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { requireUser } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import { formatDate, formatPrice, formatQty, statusTone } from "~/lib/format";
import type { OrderDetail, OrderListItem } from "~/lib/types";

import type { Route } from "./+types/order";

export const meta: Route.MetaFunction = ({ params, matches }) => [
  { title: tFromMatches(matches)("account.order", { id: params.id ?? "" }) },
];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  requireUser(request, context);
  const api = context.get(apiContext);
  try {
    const [order, list] = await Promise.all([
      api.get<OrderDetail>(`/orders/history/${params.id}/`),
      api.get<OrderListItem[]>("/orders/history/"),
    ]);
    const canCancel = list.find((o) => String(o.id) === params.id)?.can_be_canceled ?? false;
    return { order, canCancel };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data(makeT(langFromRequest(request))("account.orderNotFound"), { status: 404 });
    throw e;
  }
}

export async function action({ request, params, context }: Route.ActionArgs) {
  requireUser(request, context);
  try {
    await context.get(apiContext).post(`/orders/history/${params.id}/cancel/`);
    return { error: null };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ error: e.fieldErrors.form ?? makeT(langFromRequest(request))("account.cancelError") }, { status: 400 });
  }
}

export default function Order({ loaderData, actionData }: Route.ComponentProps) {
  const { order, canCancel } = loaderData;
  const canceling = useNavigation().state === "submitting";
  const t = useT();
  const lang = useLang();
  const local = useLocalPath();
  return (
    <div className="space-y-4">
      <Link to="/account/orders" className="text-sm text-brand-600 hover:underline">{t("account.allOrders")}</Link>
      <PageTitle subtitle={formatDate(order.creation_date, lang)}>{t("account.order", { id: order.number_order })}</PageTitle>
      {actionData?.error && <Alert tone="danger">{actionData.error}</Alert>}
      <div className="flex flex-wrap gap-2">
        <Badge tone={statusTone(order.status_order)}>{order.status_order_display}</Badge>
        <Badge tone="muted">{order.payment_type_display}</Badge>
        <Badge tone="muted">{order.payment_status_display}</Badge>
      </div>
      {order.ttn && (
        <Alert>
          {t("account.ttn", { ttn: order.ttn })}
          {order.ttn_status && ` — ${order.ttn_status}`}{" "}
          <a href={`https://novaposhta.ua/tracking/?cargo_number=${order.ttn}`} target="_blank" rel="noreferrer" className="font-semibold underline">
            {t("account.track")}
          </a>
        </Alert>
      )}
      {order.can_download_invoice && (
        <a href={local(`/account/orders/${order.number_order}/invoice`)} target="_blank" rel="noreferrer" className="inline-block text-sm font-semibold text-brand-700 hover:underline">
          {t("account.invoice")}
        </a>
      )}
      <Card className="divide-y divide-line">
        {order.list_of_products.map((line) => (
          <div key={line.variant.id} className="flex items-center gap-4 p-4">
            {line.photo && <img src={line.photo} alt="" className="size-14 rounded-lg bg-surface object-contain" />}
            <div className="flex-1">
              <p className="font-medium">{line.name}</p>
              <p className="text-sm text-muted">
                {formatQty(line.quantity)} × {formatPrice(line.price)}
                {line.sku && ` · ${t("account.skuShort")} ${line.sku}`}
              </p>
            </div>
            <span className="font-semibold">{formatPrice(line.total)}</span>
          </div>
        ))}
        <div className="flex justify-between p-4 text-lg font-bold">
          <span>{t("cart.total")}</span>
          <span>{formatPrice(order.total_price)}</span>
        </div>
      </Card>
      <Card className="space-y-1 p-4 text-sm">
        <p><span className="text-muted">{t("account.recipient")}:</span> {order.customer_name}</p>
        <p><span className="text-muted">{t("account.deliveryTo")}:</span> {order.address}</p>
        {order.comment && <p><span className="text-muted">{t("account.comment")}:</span> {order.comment}</p>}
      </Card>
      {canCancel && (
        <Form method="post" onSubmit={(e) => !confirm(t("account.cancelConfirm")) && e.preventDefault()}>
          <Button type="submit" variant="secondary" loading={canceling}>{t("account.cancel")}</Button>
        </Form>
      )}
    </div>
  );
}
