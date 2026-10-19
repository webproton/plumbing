import { Save } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { NpPicker } from "~/components/NpPicker";
import { Alert, Button, Card, Field, Input, PageTitle, Textarea } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";

import type { Route } from "./+types/settings";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("set.nav") }];

interface ShopSettings {
  phone: string;
  email: string | null;
  telegram: string | null;
  whatsapp: string | null;
  legal_name: string;
  tax_id: string;
  iban: string;
  bank_name: string;
  legal_address: string;
  vat_payer: boolean;
  invoice_note: string;
  np_sender_city_ref: string;
  np_sender_city_name: string;
  np_sender_warehouse_ref: string;
  np_sender_warehouse_name: string;
  np_sender_phone: string;
  np_key_configured: boolean;
}

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  try {
    return { settings: await api.get<ShopSettings>("/callback/shop-settings/") };
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) throw data({ pending: false }, { status: 403 });
    throw e;
  }
}

const TEXT_FIELDS = [
  "phone", "email", "telegram", "whatsapp", "legal_name", "tax_id", "iban", "bank_name", "legal_address",
  "invoice_note", "np_sender_city_ref", "np_sender_city_name", "np_sender_warehouse_ref", "np_sender_warehouse_name",
  "np_sender_phone",
] as const; // prettier-ignore

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const t = makeT(langFromRequest(request));
  const form = await request.formData();
  const body: Record<string, unknown> = { vat_payer: form.get("vat_payer") === "1" };
  for (const f of TEXT_FIELDS) body[f] = String(form.get(f) ?? "").trim();
  for (const f of ["email", "telegram", "whatsapp"]) if (!body[f]) body[f] = null;
  if (!body.np_sender_city_ref)
    Object.assign(body, {
      np_sender_city_name: "",
      np_sender_warehouse_ref: "",
      np_sender_warehouse_name: "",
    });
  try {
    await api.patch("/callback/shop-settings/", body);
    return { ok: true as const, errors: {} as Record<string, string> };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors = Object.keys(e.fieldErrors).length ? e.fieldErrors : { form: t("error.generic") };
    return data({ ok: false as const, errors }, { status: 400 });
  }
}

export default function Settings({ loaderData, actionData }: Route.ComponentProps) {
  const { settings: s } = loaderData;
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const errors: Record<string, string> = actionData?.errors ?? {};
  const text = (name: (typeof TEXT_FIELDS)[number], label: string, hint?: string) => (
    <Field label={label} hint={hint} error={errors[name]}>
      {(p) => <Input {...p} name={name} defaultValue={(s[name] as string | null) ?? ""} />}
    </Field>
  );
  const number = /№\s*(\d+)/.exec(s.np_sender_warehouse_name)?.[1] ?? "";

  return (
    <div className="max-w-4xl space-y-5">
      <PageTitle subtitle={t("set.subtitle")}>{t("set.nav")}</PageTitle>
      {actionData?.ok && <Alert tone="success">{t("prod.saved")}</Alert>}
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}
      <Form method="post" className="space-y-5">
        <Card className="space-y-4 p-5">
          <h2 className="font-semibold">{t("set.contacts")}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {text("phone", t("checkout.phone"))}
            {text("email", "Email")}
            {text("telegram", "Telegram", "https://t.me/…")}
            {text("whatsapp", "WhatsApp", "https://wa.me/380…")}
          </div>
        </Card>
        <Card className="space-y-4 p-5">
          <h2 className="font-semibold">{t("set.requisites")}</h2>
          <p className="text-muted text-sm">{t("set.requisitesHint")}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {text("legal_name", t("set.legalName"), t("set.legalNameHint"))}
            {text("tax_id", t("set.taxId"))}
            {text("iban", "IBAN", "UA…")}
            {text("bank_name", t("set.bank"))}
            {text("legal_address", t("set.address"))}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              name="vat_payer"
              value="1"
              defaultChecked={s.vat_payer}
              className="accent-brand-600 size-4"
            />
            {t("set.vatPayer")}
          </label>
          <Field label={t("set.invoiceNote")} error={errors.invoice_note}>
            {(p) => <Textarea {...p} name="invoice_note" rows={2} defaultValue={s.invoice_note} />}
          </Field>
        </Card>
        <Card className="space-y-4 p-5">
          <h2 className="font-semibold">{t("set.np")}</h2>
          <p className="text-muted text-sm">{t("set.npHint")}</p>
          <NpPicker
            names={{
              city: "np_sender_city_name",
              department: "np_sender_department",
              cityRef: "np_sender_city_ref",
              warehouseRef: "np_sender_warehouse_ref",
              warehouseName: "np_sender_warehouse_name",
            }}
            initial={{
              cityName: s.np_sender_city_name,
              cityRef: s.np_sender_city_ref,
              warehouseRef: s.np_sender_warehouse_ref,
              warehouseName: s.np_sender_warehouse_name,
              department: number,
            }}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            {text("np_sender_phone", t("set.senderPhone"), "+380…")}
          </div>
          <p className={`text-sm ${s.np_key_configured ? "text-success" : "text-muted"}`}>
            {s.np_key_configured ? t("set.npKeyOn") : t("set.npKeyOff")}
          </p>
        </Card>
        <Button type="submit" size="lg" loading={busy}>
          <Save className="size-4" aria-hidden /> {t("prod.save")}
        </Button>
      </Form>
    </div>
  );
}
