import { ArrowRight, FileText, Mail, Phone, RefreshCw, Save, Truck, UserCheck, XCircle } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import {
  Alert,
  Badge,
  Button,
  buttonClass,
  Card,
  Field,
  Input,
  PageTitle,
  Select,
  Textarea,
} from "~/components/ui";
import { langFromRequest, makeT, tFromMatches, type TKey } from "~/i18n";
import { Link, useLang, useLocalPath, useT } from "~/i18n/react";
import { ApiError, LONG_TIMEOUT } from "~/lib/api.server";
import { formatDateTime, formatPrice, formatQty, paymentTone, statusTone } from "~/lib/format";
import { requireSeller } from "~/lib/seller.server";
import type { ManageOrder, PaymentStatus } from "~/lib/types";
import { thumb } from "~/lib/thumb";

import type { Route } from "./+types/order";

export const meta: Route.MetaFunction = ({ params, matches }) => [
  { title: tFromMatches(matches)("ord.title", { id: params.id ?? "" }) },
];

const PAYMENT: PaymentStatus[] = ["waiting_for_payment", "paid_for", "returning", "returned", "canceled"];

export async function loader({ request, params, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  try {
    return { order: await api.get<ManageOrder>(`/orders/manage/${params.id}/`) };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw data("Not Found", { status: 404 });
    throw e;
  }
}

export async function action({ request, params, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const intent = String(form.get("intent"));
  const base = `/orders/manage/${params.id}`;
  try {
    if (intent === "status") await api.post(`${base}/status/`, { status: form.get("status") });
    if (intent === "payment")
      await api.post(`${base}/payment/`, { payment_status: form.get("payment_status") });
    if (intent === "note") await api.post(`${base}/note/`, { manager_note: form.get("manager_note") ?? "" });
    if (intent === "assign") await api.post(`${base}/assign/`);
    if (intent === "ttn") await api.post(`${base}/ttn/`, { ttn: form.get("ttn") ?? "" });
    if (intent === "ttn_refresh") await api.post(`${base}/ttn/refresh/`);
    if (intent === "mail_resend")
      await api.post(`${base}/notifications/${Number(form.get("id"))}/resend/`, undefined, {
        timeoutMs: LONG_TIMEOUT,
      });
    if (intent === "ttn_create")
      await api.post(
        `${base}/ttn/create/`,
        {
          weight: form.get("weight"),
          seats: form.get("seats"),
          description: form.get("description") ?? "",
          payer: form.get("payer"),
          cod: form.get("cod") === "1",
        },
        { timeoutMs: LONG_TIMEOUT },
      );
    if (intent === "invoice_send") {
      const r = await api.post<{ sent_to: string }>(`${base}/invoice/send/`, undefined, {
        timeoutMs: LONG_TIMEOUT,
      });
      return { ok: true as const, intent, error: null, sentTo: r.sent_to };
    }
    return { ok: true as const, intent, error: null };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data(
      { ok: false as const, intent, error: Object.values(e.fieldErrors)[0] ?? t("error.generic") },
      { status: 400 },
    );
  }
}

export default function OrderPage({ loaderData, actionData }: Route.ComponentProps) {
  const { order } = loaderData;
  const t = useT();
  const lang = useLang();
  const nav = useNavigation();
  const busy = (intent: string) => nav.state !== "idle" && nav.formData?.get("intent") === intent;
  const saved = (intent: string) => actionData?.ok && actionData.intent === intent;
  const phone = order.phone_number?.replace(/[^\d+]/g, "");

  return (
    <div className="max-w-5xl space-y-5">
      <Link to="/seller/orders" className="text-brand-600 text-sm hover:underline">
        {t("ord.back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <PageTitle subtitle={formatDateTime(order.creation_date, lang)}>
          {t("ord.title", { id: order.id })}
        </PageTitle>
        <Badge tone={statusTone(order.status_order)}>{order.status_display}</Badge>
        <Badge tone={paymentTone(order.payment_status)}>{order.payment_status_display}</Badge>
        {order.channel === "pos" && <Badge tone="info">{t("ord.channel.pos")}</Badge>}
        <span className="text-muted text-sm">{t(`ord.stock.${order.stock_state}` as TKey)}</span>
      </div>
      {actionData && !actionData.ok && <Alert tone="danger">{actionData.error}</Alert>}
      {saved("mail_resend") && <Alert tone="success">{t("ord.mail.resent")}</Alert>}
      {actionData?.ok && "sentTo" in actionData && (
        <Alert tone="success">{t("ord.invoice.sent", { email: actionData.sentTo ?? "" })}</Alert>
      )}
      {!order.can_manage && <Alert>{t("ord.readOnly")}</Alert>}

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-1.5 p-5 text-sm">
          <h2 className="mb-1 font-semibold">{t("ord.customer")}</h2>
          <p className="text-base font-medium">{order.customer_name}</p>
          {phone && (
            <a
              href={`tel:${phone}`}
              className="text-brand-700 inline-flex items-center gap-1.5 hover:underline"
            >
              <Phone className="size-4" aria-hidden /> {order.phone_number}
            </a>
          )}
          {(order.email || order.customer_email) && <p>{order.email || order.customer_email}</p>}
          {(order.telegram || order.whatsapp) && (
            <p className="text-muted">
              {[
                order.telegram && `Telegram ${order.telegram}`,
                order.whatsapp && `WhatsApp ${order.whatsapp}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </Card>
        <Card className="space-y-1.5 p-5 text-sm">
          <h2 className="mb-1 font-semibold">{t("ord.delivery")}</h2>
          <p>{order.address}</p>
          {order.channel === "pos" ? (
            <p className="text-muted">
              {t("ord.paymentMethod")}: {order.payment_method_display}
              {order.discount_percent > 0 && ` · ${t("ord.discount", { value: order.discount_percent })}`}
            </p>
          ) : (
            <p className="text-muted">
              {t("ord.paymentType")}: {order.payment_type_display}
            </p>
          )}
          {order.comment && (
            <>
              <h3 className="pt-2 font-semibold">{t("ord.comment")}</h3>
              <p className="whitespace-pre-line">{order.comment}</p>
            </>
          )}
        </Card>
      </div>

      <section className="space-y-2">
        <h2 className="font-semibold">{t("ord.goods")}</h2>
        <TableWrap>
          <Table>
            <thead>
              <tr>
                <Th>{t("wh.col.product")}</Th>
                <Th align="right">{t("ord.col.qty")}</Th>
                <Th align="right">{t("ord.col.price")}</Th>
                <Th align="right">{t("ord.col.lineTotal")}</Th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((it) => (
                <tr key={it.id}>
                  <Td>
                    <div className="flex items-center gap-3">
                      {it.photo ? (
                        <img
                          src={thumb(it.photo, 160)}
                          alt=""
                          loading="lazy"
                          className="border-line size-11 shrink-0 rounded-lg border object-contain"
                        />
                      ) : (
                        <span className="bg-surface size-11 shrink-0 rounded-lg" />
                      )}
                      <div>
                        {it.product ? (
                          <Link
                            to={`/seller/products/${it.product}`}
                            className="text-brand-700 font-medium hover:underline"
                          >
                            {it.name}
                          </Link>
                        ) : (
                          <p className="font-medium">{it.name}</p>
                        )}
                        <p className="text-muted text-xs">
                          {it.sku && `${it.sku} · `}
                          {t("ord.stockNow", { qty: formatQty(it.available_stock) })}
                        </p>
                        {it.on_order && (
                          <p className="text-brand-700 text-xs font-medium">
                            {it.supplier_name
                              ? t("ord.onOrderFrom", { supplier: it.supplier_name })
                              : t("ord.onOrder")}
                          </p>
                        )}
                      </div>
                    </div>
                  </Td>
                  <Td align="right">{formatQty(it.quantity)}</Td>
                  <Td align="right">{formatPrice(it.unit_price)}</Td>
                  <Td align="right">{formatPrice(it.line_total)}</Td>
                </tr>
              ))}
              <tr>
                <Td colSpan={3} className="text-right font-semibold">
                  {t("ord.total")}
                </Td>
                <Td align="right" className="font-semibold">
                  {formatPrice(order.total_price)}
                </Td>
              </tr>
            </tbody>
          </Table>
        </TableWrap>
      </section>

      <DeliveryCard order={order} />
      <MailCard order={order} />

      {order.can_manage && (
        <Card className="space-y-4 p-5">
          <h2 className="font-semibold">{t("ord.actions")}</h2>
          {order.next_statuses.length === 0 ? (
            <p className="text-muted text-sm">{t("ord.final")}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {order.next_statuses.map((s) => {
                const cancel = s.value === "canceled";
                const ships = s.value === "delivered" || s.value === "completed";
                const question = cancel
                  ? t("ord.cancelConfirm")
                  : ships && order.stock_state !== "written_off"
                    ? t("ord.shipConfirm", { status: s.label })
                    : null;
                return (
                  <Form
                    key={s.value}
                    method="post"
                    onSubmit={(e) => question && !confirm(question) && e.preventDefault()}
                  >
                    <input type="hidden" name="intent" value="status" />
                    <input type="hidden" name="status" value={s.value} />
                    <Button
                      type="submit"
                      size="sm"
                      variant={cancel ? "ghost" : "primary"}
                      className={cancel ? "text-danger" : undefined}
                      loading={busy("status") && nav.formData?.get("status") === s.value}
                    >
                      {cancel ? (
                        <XCircle className="size-4" aria-hidden />
                      ) : (
                        <ArrowRight className="size-4" aria-hidden />
                      )}
                      {t("ord.moveTo", { status: s.label })}
                    </Button>
                  </Form>
                );
              })}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Form method="post" className="flex items-end gap-2">
              <input type="hidden" name="intent" value="payment" />
              <Field label={t("ord.paymentStatus")}>
                {(p) => (
                  <Select
                    {...p}
                    name="payment_status"
                    defaultValue={order.payment_status}
                    key={order.payment_status}
                  >
                    {PAYMENT.map((v) => (
                      <option key={v} value={v}>
                        {t(`ord.pay.${v}` as TKey)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Button type="submit" variant="secondary" loading={busy("payment")}>
                <Save className="size-4" aria-hidden />
              </Button>
              {saved("payment") && <span className="text-success pb-3 text-sm">{t("ord.saved")}</span>}
            </Form>
            <div className="flex items-end gap-3 text-sm">
              {order.manager_email && (
                <p className="text-muted pb-3">{t("ord.manager", { email: order.manager_email })}</p>
              )}
              <Form method="post">
                <input type="hidden" name="intent" value="assign" />
                <Button type="submit" variant="ghost" size="sm" loading={busy("assign")}>
                  <UserCheck className="size-4" aria-hidden /> {t("ord.assignMe")}
                </Button>
              </Form>
            </div>
          </div>

          <Form method="post" className="space-y-2">
            <input type="hidden" name="intent" value="note" />
            <Field label={t("ord.note")} hint={t("ord.noteHint")}>
              {(p) => (
                <Textarea
                  {...p}
                  name="manager_note"
                  rows={3}
                  defaultValue={order.manager_note}
                  maxLength={2000}
                />
              )}
            </Field>
            <div className="flex items-center gap-2">
              <Button type="submit" size="sm" variant="secondary" loading={busy("note")}>
                <Save className="size-4" aria-hidden /> {t("ord.save")}
              </Button>
              {saved("note") && <span className="text-success text-sm">{t("ord.saved")}</span>}
            </div>
          </Form>
        </Card>
      )}
    </div>
  );
}

const MAIL_TONE = { sent: "success", failed: "danger", pending: "muted" } as const;

/** Письма покупателю: что и когда ушло, ошибки отправки, «Надіслати ще раз» */
function MailCard({ order }: { order: ManageOrder }) {
  const t = useT();
  const lang = useLang();
  const nav = useNavigation();
  const hasEmail = Boolean(order.email || order.customer_email);
  const customerLang = t(`ord.mail.lang.${order.language === "ru" ? "ru" : "uk"}` as TKey);

  return (
    <Card className="space-y-3 p-5 text-sm">
      <h2 className="flex items-center gap-2 font-semibold">
        <Mail className="size-4" aria-hidden /> {t("ord.mail.title")}
      </h2>
      <p className="text-muted">{t("ord.mail.hint", { lang: customerLang })}</p>
      {!order.notify_customers && <Alert>{t("ord.mail.off")}</Alert>}
      {!hasEmail ? (
        <p className="text-muted">{t("ord.mail.noEmail")}</p>
      ) : order.notifications.length === 0 ? (
        <p className="text-muted">{t("ord.mail.empty")}</p>
      ) : (
        <ul className="divide-line divide-y">
          {order.notifications.map((n) => (
            <li key={n.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
              <span className="font-medium">{t(`ord.mail.event.${n.event}` as TKey)}</span>
              {n.ttn && (n.event === "ttn" || n.event === "shipped") && (
                <span className="text-muted">{n.ttn}</span>
              )}
              <Badge tone={MAIL_TONE[n.status]}>{t(`ord.mail.status.${n.status}` as TKey)}</Badge>
              <span className="text-muted">
                {n.recipient} · {formatDateTime(n.sent_at ?? n.created_at, lang)}
              </span>
              {n.error && <span className="text-danger w-full text-xs">{n.error}</span>}
              {order.can_manage && (
                <Form method="post" className="ml-auto">
                  <input type="hidden" name="intent" value="mail_resend" />
                  <input type="hidden" name="id" value={n.id} />
                  <Button
                    type="submit"
                    size="sm"
                    variant="ghost"
                    loading={nav.state !== "idle" && nav.formData?.get("id") === String(n.id)}
                  >
                    <RefreshCw className="size-4" aria-hidden /> {t("ord.mail.resend")}
                  </Button>
                </Form>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function DeliveryCard({ order }: { order: ManageOrder }) {
  const t = useT();
  const lang = useLang();
  const local = useLocalPath();
  const nav = useNavigation();
  const busy = (intent: string) => nav.state !== "idle" && nav.formData?.get("intent") === intent;
  const tools = order.delivery_tools;
  const pickup = !order.city && !order.np_warehouse_ref;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card className="space-y-3 p-5 text-sm">
        <h2 className="flex items-center gap-2 font-semibold">
          <Truck className="size-4" aria-hidden /> {t("ord.np.title")}
        </h2>
        {order.ttn ? (
          <div className="space-y-1">
            <p>
              {t("ord.np.ttn")}:{" "}
              <a
                href={`https://novaposhta.ua/tracking/?cargo_number=${order.ttn}`}
                target="_blank"
                rel="noreferrer"
                className="text-brand-700 font-semibold hover:underline"
              >
                {order.ttn}
              </a>
            </p>
            {order.ttn_status && (
              <p>
                {order.ttn_status}
                {order.ttn_updated_at && (
                  <span className="text-muted"> · {formatDateTime(order.ttn_updated_at, lang)}</span>
                )}
              </p>
            )}
            {order.can_manage && (
              <Form method="post">
                <input type="hidden" name="intent" value="ttn_refresh" />
                <Button type="submit" size="sm" variant="ghost" loading={busy("ttn_refresh")}>
                  <RefreshCw className="size-3.5" aria-hidden /> {t("ord.np.refresh")}
                </Button>
              </Form>
            )}
          </div>
        ) : (
          <p className="text-muted">{pickup ? t("ord.np.pickup") : t("ord.np.noTtn")}</p>
        )}
        {order.can_manage && !pickup && (
          <Form method="post" className="flex items-end gap-2">
            <input type="hidden" name="intent" value="ttn" />
            <Field label={order.ttn ? t("ord.np.change") : t("ord.np.manual")} hint={t("ord.np.manualHint")}>
              {(p) => (
                <Input
                  {...p}
                  name="ttn"
                  defaultValue={order.ttn}
                  inputMode="numeric"
                  placeholder="20450000000000"
                  className="w-48"
                />
              )}
            </Field>
            <Button type="submit" size="sm" variant="secondary" loading={busy("ttn")} className="mb-6">
              <Save className="size-3.5" aria-hidden />
            </Button>
          </Form>
        )}
        {order.can_manage && !order.ttn && tools.can_create_ttn && (
          <details className="border-line rounded-xl border p-3">
            <summary className="cursor-pointer font-medium">{t("ord.np.create")}</summary>
            <Form method="post" className="mt-3 grid gap-3 sm:grid-cols-2">
              <input type="hidden" name="intent" value="ttn_create" />
              <Field label={t("ord.np.weight")}>
                {(p) => (
                  <Input {...p} name="weight" type="number" min="0.1" step="0.1" defaultValue="1" required />
                )}
              </Field>
              <Field label={t("ord.np.seats")}>
                {(p) => (
                  <Input {...p} name="seats" type="number" min="1" max="50" defaultValue="1" required />
                )}
              </Field>
              <Field label={t("ord.np.description")}>
                {(p) => (
                  <Input
                    {...p}
                    name="description"
                    maxLength={100}
                    placeholder={t("ord.np.descriptionPlaceholder")}
                  />
                )}
              </Field>
              <Field label={t("ord.np.payer")}>
                {(p) => (
                  <Select {...p} name="payer" defaultValue="Recipient">
                    <option value="Recipient">{t("ord.np.payerRecipient")}</option>
                    <option value="Sender">{t("ord.np.payerSender")}</option>
                  </Select>
                )}
              </Field>
              <label className="flex items-center gap-2 sm:col-span-2">
                <input
                  type="checkbox"
                  name="cod"
                  value="1"
                  defaultChecked={order.payment_status !== "paid_for"}
                  className="accent-brand-600 size-4"
                />
                {t("ord.np.cod", { sum: formatPrice(order.total_price) })}
              </label>
              <Button
                type="submit"
                size="sm"
                loading={busy("ttn_create")}
                className="sm:col-span-2 sm:justify-self-start"
              >
                <Truck className="size-3.5" aria-hidden /> {t("ord.np.createSubmit")}
              </Button>
            </Form>
          </details>
        )}
        {order.can_manage && !order.ttn && !pickup && !tools.can_create_ttn && (
          <p className="text-muted text-xs">
            {!tools.np_key
              ? t("ord.np.noKey")
              : !tools.sender_ready
                ? t("ord.np.noSender")
                : t("ord.np.noRef")}
          </p>
        )}
      </Card>

      <Card className="space-y-3 p-5 text-sm">
        <h2 className="flex items-center gap-2 font-semibold">
          <FileText className="size-4" aria-hidden /> {t("ord.invoice.title")}
        </h2>
        {tools.has_requisites ? (
          <div className="flex flex-wrap gap-2">
            <a
              href={local(`/seller/orders/${order.id}/invoice`)}
              target="_blank"
              rel="noreferrer"
              className={buttonClass("secondary", "sm")}
            >
              <FileText className="size-3.5" aria-hidden /> {t("ord.invoice.pdf")}
            </a>
            {order.can_manage && (order.email || order.customer_email) && (
              <Form method="post">
                <input type="hidden" name="intent" value="invoice_send" />
                <Button type="submit" size="sm" variant="ghost" loading={busy("invoice_send")}>
                  <Mail className="size-3.5" aria-hidden />{" "}
                  {t("ord.invoice.send", { email: order.email || order.customer_email || "" })}
                </Button>
              </Form>
            )}
          </div>
        ) : (
          <p className="text-muted">
            {t("ord.invoice.noRequisites")}{" "}
            <Link to="/seller/settings" className="text-brand-700 hover:underline">
              {t("set.nav")}
            </Link>
          </p>
        )}
      </Card>
    </div>
  );
}
