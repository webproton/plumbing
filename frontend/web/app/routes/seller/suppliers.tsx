import { Pencil, Plus, Save, Trash2 } from "lucide-react";
import { data, Form, useNavigation, useSearchParams } from "react-router";

import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, Button, ButtonLink, Card, Field, Input, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";
import type { Supplier } from "~/lib/types";
import { formObject } from "~/lib/validation";

import type { Route } from "./+types/suppliers";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("wh.nav.suppliers") },
];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  return { suppliers: (await api.get<Supplier[]>("/warehouse/suppliers/")).filter((s) => s.is_active) };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const v = formObject(await request.formData());
  try {
    if (v.intent === "create") {
      await api.post("/warehouse/suppliers/", {
        name: v.name,
        code: v.code ?? "",
        contact_person: v.contact_person ?? "",
        phone: v.phone ?? "",
        email: v.email ?? "",
        address: "",
      });
    } else if (v.intent === "update") {
      await api.patch(`/warehouse/suppliers/${Number(v.id)}/`, {
        name: v.name,
        code: v.code ?? "",
        contact_person: v.contact_person ?? "",
        phone: v.phone ?? "",
        email: v.email ?? "",
        address: v.address ?? "",
      });
      return { ok: true as const, updated: true };
    } else if (v.intent === "delete") {
      await api.delete(`/warehouse/suppliers/${Number(v.id)}/`);
    }
    return { ok: true as const, updated: false };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ ok: false as const, errors: e.fieldErrors }, { status: 400 });
  }
}

export default function Suppliers({ loaderData, actionData }: Route.ComponentProps) {
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const errors = actionData && !actionData.ok ? actionData.errors : {};
  const [params] = useSearchParams();
  const editId = actionData?.ok && actionData.updated ? null : Number(params.get("edit")) || null;
  const editing = loaderData.suppliers.find((s) => s.id === editId);
  return (
    <div className="space-y-5">
      <PageTitle subtitle={t("wh.sup.subtitle")} help="suppliers">
        {t("wh.nav.suppliers")}
      </PageTitle>
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}

      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th>{t("wh.wh.name")}</Th>
              <Th>{t("wh.sup.code")}</Th>
              <Th>{t("wh.sup.contact")}</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {loaderData.suppliers.length === 0 && (
              <tr>
                <Td colSpan={4} className="text-muted py-8 text-center">
                  {t("wh.sup.empty")}
                </Td>
              </tr>
            )}
            {loaderData.suppliers.map((s) => (
              <tr key={s.id}>
                <Td className="font-medium">{s.name}</Td>
                <Td className="text-muted">{s.code || "—"}</Td>
                <Td className="text-muted">
                  {[s.contact_person, s.phone, s.email].filter(Boolean).join(" · ") || "—"}
                </Td>
                <Td className="text-right">
                  <div className="flex justify-end gap-1">
                    <ButtonLink
                      to={`/seller/suppliers?edit=${s.id}`}
                      size="sm"
                      variant="ghost"
                      aria-label={t("wh.sup.edit")}
                      title={t("wh.sup.edit")}
                    >
                      <Pencil className="size-3.5" aria-hidden />
                    </ButtonLink>
                    <Form
                      method="post"
                      onSubmit={(e) => !confirm(t("wh.sup.confirmDelete")) && e.preventDefault()}
                    >
                      <input type="hidden" name="intent" value="delete" />
                      <input type="hidden" name="id" value={s.id} />
                      <Button type="submit" size="sm" variant="ghost" aria-label={t("cart.remove")}>
                        <Trash2 className="size-3.5" aria-hidden />
                      </Button>
                    </Form>
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </TableWrap>

      {actionData?.ok && actionData.updated && <Alert tone="success">{t("wh.sup.saved")}</Alert>}

      {editing && (
        <Card className="border-brand-500 border-2 p-5">
          <h2 className="mb-3 font-semibold">{t("wh.sup.editTitle", { name: editing.name })}</h2>
          <Form method="post" className="space-y-4" key={editing.id}>
            <input type="hidden" name="intent" value="update" />
            <input type="hidden" name="id" value={editing.id} />
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label={t("wh.wh.name")} error={errors.name}>
                {(p) => <Input {...p} name="name" required defaultValue={editing.name} />}
              </Field>
              <Field label={t("wh.sup.code")} error={errors.code} hint={t("wh.sup.codeHint")}>
                {(p) => <Input {...p} name="code" defaultValue={editing.code} />}
              </Field>
              <Field label={t("wh.sup.contactPerson")} error={errors.contact_person}>
                {(p) => <Input {...p} name="contact_person" defaultValue={editing.contact_person} />}
              </Field>
              <Field label={t("checkout.phone")} error={errors.phone}>
                {(p) => <Input {...p} name="phone" type="tel" defaultValue={editing.phone} />}
              </Field>
              <Field label="Email" error={errors.email}>
                {(p) => <Input {...p} name="email" type="email" defaultValue={editing.email} />}
              </Field>
              <Field label={t("wh.sup.address")} error={errors.address}>
                {(p) => <Input {...p} name="address" defaultValue={editing.address} />}
              </Field>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={busy}>
                <Save className="size-4" aria-hidden /> {t("wh.sup.save")}
              </Button>
              <ButtonLink to="/seller/suppliers" variant="secondary">
                {t("wh.sup.cancel")}
              </ButtonLink>
            </div>
          </Form>
        </Card>
      )}

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">{t("wh.sup.add")}</h2>
        <Form method="post" className="space-y-4">
          <input type="hidden" name="intent" value="create" />
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t("wh.wh.name")} error={errors.name}>
              {(p) => <Input {...p} name="name" required />}
            </Field>
            <Field label={t("wh.sup.code")} error={errors.code} hint={t("wh.sup.codeHint")}>
              {(p) => <Input {...p} name="code" placeholder="aquadom" />}
            </Field>
            <Field label={t("wh.sup.contactPerson")} error={errors.contact_person}>
              {(p) => <Input {...p} name="contact_person" />}
            </Field>
            <Field label={t("checkout.phone")} error={errors.phone}>
              {(p) => <Input {...p} name="phone" type="tel" placeholder="+380 50 123 45 67" />}
            </Field>
            <Field label="Email" error={errors.email}>
              {(p) => <Input {...p} name="email" type="email" />}
            </Field>
          </div>
          <Button type="submit" loading={busy}>
            <Plus className="size-4" aria-hidden /> {t("wh.sup.create")}
          </Button>
        </Form>
      </Card>
    </div>
  );
}
