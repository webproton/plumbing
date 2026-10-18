import { Plus, Star, Trash2 } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { Table, TableWrap, Td, Th } from "~/components/seller/Table";
import { Alert, Badge, Button, Card, Field, Input, PageTitle } from "~/components/ui";
import { tFromMatches } from "~/i18n";
import { useT } from "~/i18n/react";
import { ApiError } from "~/lib/api.server";
import { requireSeller } from "~/lib/seller.server";
import type { WarehouseRow } from "~/lib/types";
import { formObject } from "~/lib/validation";

import type { Route } from "./+types/warehouses";

export const meta: Route.MetaFunction = ({ matches }) => [{ title: tFromMatches(matches)("wh.nav.warehouses") }];

export async function loader({ request, context }: Route.LoaderArgs) {
  const api = requireSeller(request, context);
  return { warehouses: await api.get<WarehouseRow[]>("/warehouse/warehouses/") };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = requireSeller(request, context);
  const v = formObject(await request.formData());
  try {
    if (v.intent === "create") {
      await api.post("/warehouse/warehouses/", { name: v.name, address: v.address ?? "", is_default: v.is_default === "1" });
    } else if (v.intent === "default") {
      await api.patch(`/warehouse/warehouses/${Number(v.id)}/`, { is_default: true });
    } else if (v.intent === "delete") {
      await api.delete(`/warehouse/warehouses/${Number(v.id)}/`);
    }
    return { ok: true as const };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ ok: false as const, errors: e.fieldErrors }, { status: 400 });
  }
}

export default function Warehouses({ loaderData, actionData }: Route.ComponentProps) {
  const t = useT();
  const busy = useNavigation().state === "submitting";
  const errors = actionData && !actionData.ok ? actionData.errors : {};
  return (
    <div className="space-y-5">
      <PageTitle subtitle={t("wh.wh.subtitle")}>{t("wh.nav.warehouses")}</PageTitle>
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}

      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th>{t("wh.wh.name")}</Th>
              <Th>{t("wh.wh.address")}</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {loaderData.warehouses.map((w) => (
              <tr key={w.id}>
                <Td className="font-medium">
                  {w.name} {w.is_default && <Badge tone="success">{t("wh.wh.default")}</Badge>}
                </Td>
                <Td className="text-muted">{w.address || "—"}</Td>
                <Td className="text-right">
                  <div className="flex justify-end gap-2">
                    {!w.is_default && (
                      <Form method="post">
                        <input type="hidden" name="intent" value="default" />
                        <input type="hidden" name="id" value={w.id} />
                        <Button type="submit" size="sm" variant="secondary" loading={busy}>
                          <Star className="size-3.5" aria-hidden /> {t("wh.wh.makeDefault")}
                        </Button>
                      </Form>
                    )}
                    <Form method="post" onSubmit={(e) => !confirm(t("wh.wh.confirmDelete")) && e.preventDefault()}>
                      <input type="hidden" name="intent" value="delete" />
                      <input type="hidden" name="id" value={w.id} />
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

      <Card className="p-5">
        <h2 className="mb-3 font-semibold">{t("wh.wh.add")}</h2>
        <Form method="post" className="grid items-end gap-4 sm:grid-cols-[1fr_1.5fr_auto]">
          <input type="hidden" name="intent" value="create" />
          <Field label={t("wh.wh.name")} error={errors.name}>
            {(p) => <Input {...p} name="name" required />}
          </Field>
          <Field label={t("wh.wh.address")} error={errors.address}>
            {(p) => <Input {...p} name="address" />}
          </Field>
          <Button type="submit" loading={busy}>
            <Plus className="size-4" aria-hidden /> {t("wh.wh.create")}
          </Button>
        </Form>
      </Card>
    </div>
  );
}
