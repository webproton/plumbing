import { data, Form, useNavigation, useSearchParams } from "react-router";

import { Alert, Button, Card, Field, Input } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { Link, useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { ApiError } from "~/lib/api.server";
import { safeNext } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";
import type { FieldErrors } from "~/lib/types";
import { formObject, schemas, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/login";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("auth.login.title") },
  { name: "robots", content: "noindex" },
];

export function loader({ request, context }: Route.LoaderArgs) {
  const session = context.get(sessionContext);
  if (session.has("user")) throw localRedirect(request, "/account");
  return { notice: session.get("notice") ?? null };
}

interface LoginResponse {
  access?: string;
  refresh?: string;
  access_token?: string;
  refresh_token?: string;
  user?: { email?: string; first_name?: string; last_name?: string };
}

export async function action({ request, context }: Route.ActionArgs) {
  const api = context.get(apiContext);
  const t = makeT(langFromRequest(request));
  const values = formObject(await request.formData());
  const parsed = schemas(t).login.safeParse(values);
  if (!parsed.success) return data({ errors: zodErrors(parsed.error), email: values.email }, { status: 400 });
  try {
    const res = await api.post<LoginResponse>("/dj-rest-auth/login/", parsed.data, { auth: false });
    const access = res.access ?? res.access_token;
    const refresh = res.refresh ?? res.refresh_token;
    if (!access || !refresh) throw new ApiError(500, { detail: t("auth.noTokens") });
    const name = [res.user?.first_name, res.user?.last_name].filter(Boolean).join(" ");
    api.signIn({ access, refresh }, { email: res.user?.email ?? parsed.data.email, name });
    return localRedirect(request, safeNext(values.next, "/account"));
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors: FieldErrors =
      e.status === 403 || e.status === 429
        ? { form: t("auth.login.tooMany") }
        : e.fieldErrors;
    return data({ errors, email: values.email }, { status: 400 });
  }
}

export default function Login({ loaderData, actionData }: Route.ComponentProps) {
  const [params] = useSearchParams();
  const errors: FieldErrors = actionData?.errors ?? {};
  const submitting = useNavigation().state === "submitting";
  const t = useT();
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6 sm:p-8">
      <h1 className="text-2xl font-bold">{t("auth.login.title")}</h1>
      {loaderData.notice && <Alert tone="success">{loaderData.notice}</Alert>}
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}
      <Form method="post" className="space-y-4" noValidate>
        <input type="hidden" name="next" value={params.get("next") ?? ""} />
        <Field label={t("auth.email")} error={errors.email}>
          {(p) => <Input {...p} name="email" type="email" autoComplete="email" defaultValue={actionData?.email} required />}
        </Field>
        <Field label={t("auth.password")} error={errors.password}>
          {(p) => <Input {...p} name="password" type="password" autoComplete="current-password" required />}
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          {t("auth.login.submit")}
        </Button>
      </Form>
      <div className="flex justify-between text-sm">
        <Link to="/register" className="text-brand-600 hover:underline">{t("auth.register.link")}</Link>
        <Link to="/reset-password" className="text-muted hover:text-ink">{t("auth.forgot")}</Link>
      </div>
    </Card>
  );
}
