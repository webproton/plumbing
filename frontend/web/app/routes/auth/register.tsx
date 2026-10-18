import { MailCheck } from "lucide-react";
import { data, Form, useNavigation } from "react-router";

import { Alert, Button, Card, EmptyState, Field, Input } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError } from "~/lib/api.server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";
import type { FieldErrors } from "~/lib/types";
import { formObject, schemas, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/register";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("auth.register.title") },
  { name: "robots", content: "noindex" },
];

export function loader({ request, context }: Route.LoaderArgs) {
  if (context.get(sessionContext).has("user")) throw localRedirect(request, "/account");
  return null;
}

export async function action({ request, context }: Route.ActionArgs) {
  const values = formObject(await request.formData());
  const parsed = schemas(makeT(langFromRequest(request))).register.safeParse(values);
  if (!parsed.success) return data({ errors: zodErrors(parsed.error), email: values.email, sent: false }, { status: 400 });
  try {
    await context.get(apiContext).post("/dj-rest-auth/registration/", parsed.data, { auth: false });
    return { errors: {} as FieldErrors, email: parsed.data.email, sent: true };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ errors: e.fieldErrors, email: values.email, sent: false }, { status: 400 });
  }
}

export default function Register({ actionData }: Route.ComponentProps) {
  const submitting = useNavigation().state === "submitting";
  const t = useT();
  if (actionData?.sent) {
    return (
      <EmptyState icon={MailCheck} title={t("auth.register.sentTitle")}>
        {t("auth.register.sentText", { email: actionData.email ?? "" })}
      </EmptyState>
    );
  }
  const errors: FieldErrors = actionData?.errors ?? {};
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6 sm:p-8">
      <h1 className="text-2xl font-bold">{t("auth.register.title")}</h1>
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}
      <Form method="post" className="space-y-4" noValidate>
        <Field label={t("auth.email")} error={errors.email}>
          {(p) => <Input {...p} name="email" type="email" autoComplete="email" defaultValue={actionData?.email} />}
        </Field>
        <Field label={t("auth.password")} error={errors.password1} hint={t("auth.register.passwordHint")}>
          {(p) => <Input {...p} name="password1" type="password" autoComplete="new-password" />}
        </Field>
        <Field label={t("auth.register.password2")} error={errors.password2}>
          {(p) => <Input {...p} name="password2" type="password" autoComplete="new-password" />}
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          {t("auth.register.submit")}
        </Button>
      </Form>
      <p className="text-center text-sm text-muted">
        {t("auth.register.haveAccount")}{" "}
        <Link to="/login" className="text-brand-600 hover:underline">{t("auth.login.submit")}</Link>
      </p>
    </Card>
  );
}
