import { data, Form, useNavigation, useSearchParams } from "react-router";

import { Alert, Button, Card, Field, Input } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError } from "~/lib/api.server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";
import type { FieldErrors } from "~/lib/types";
import { formObject } from "~/lib/validation";

import type { Route } from "./+types/reset-password-confirm";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("auth.newPassword.title") },
];

export async function action({ request, context }: Route.ActionArgs) {
  const t = makeT(langFromRequest(request));
  const v = formObject(await request.formData());
  if (v.new_password1 !== v.new_password2) {
    return data({ errors: { new_password2: t("v.passwordMismatch") } as FieldErrors }, { status: 400 });
  }
  try {
    await context.get(apiContext).post("/dj-rest-auth/password/reset/confirm/", v, { auth: false });
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors = e.fieldErrors;
    if (errors.token || errors.uid) errors.form = t("auth.newPassword.expired");
    return data({ errors }, { status: 400 });
  }
  context.get(sessionContext).flash("notice", t("auth.newPassword.done"));
  return localRedirect(request, "/login");
}

export default function ResetPasswordConfirm({ actionData }: Route.ComponentProps) {
  const [params] = useSearchParams();
  const errors: FieldErrors = actionData?.errors ?? {};
  const submitting = useNavigation().state === "submitting";
  const t = useT();
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6 sm:p-8">
      <h1 className="text-2xl font-bold">{t("auth.newPassword.title")}</h1>
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}
      <Form method="post" className="space-y-4" noValidate>
        <input type="hidden" name="uid" value={params.get("uid") ?? ""} />
        <input type="hidden" name="token" value={params.get("token") ?? ""} />
        <Field label={t("auth.newPassword.field")} error={errors.new_password1}>
          {(p) => <Input {...p} name="new_password1" type="password" autoComplete="new-password" />}
        </Field>
        <Field label={t("auth.register.password2")} error={errors.new_password2}>
          {(p) => <Input {...p} name="new_password2" type="password" autoComplete="new-password" />}
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          {t("auth.newPassword.submit")}
        </Button>
      </Form>
    </Card>
  );
}
