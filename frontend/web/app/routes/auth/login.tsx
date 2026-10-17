import { data, Form, Link, redirect, useNavigation, useSearchParams } from "react-router";

import { Alert, Button, Card, Field, Input } from "~/components/ui";
import { ApiError } from "~/lib/api.server";
import { safeNext } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";
import type { FieldErrors } from "~/lib/types";
import { formObject, loginSchema, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/login";

export const meta: Route.MetaFunction = () => [{ title: "Вход" }, { name: "robots", content: "noindex" }];

export function loader({ context }: Route.LoaderArgs) {
  const session = context.get(sessionContext);
  if (session.has("user")) throw redirect("/account");
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
  const values = formObject(await request.formData());
  const parsed = loginSchema.safeParse(values);
  if (!parsed.success) return data({ errors: zodErrors(parsed.error), email: values.email }, { status: 400 });
  try {
    const res = await api.post<LoginResponse>("/dj-rest-auth/login/", parsed.data, { auth: false });
    const access = res.access ?? res.access_token;
    const refresh = res.refresh ?? res.refresh_token;
    if (!access || !refresh) throw new ApiError(500, { detail: "Сервер не вернул токены" });
    const name = [res.user?.first_name, res.user?.last_name].filter(Boolean).join(" ");
    api.signIn({ access, refresh }, { email: res.user?.email ?? parsed.data.email, name });
    return redirect(safeNext(values.next, "/account"));
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors: FieldErrors =
      e.status === 403 || e.status === 429
        ? { form: "Слишком много попыток входа. Попробуйте через час." }
        : e.fieldErrors;
    return data({ errors, email: values.email }, { status: 400 });
  }
}

export default function Login({ loaderData, actionData }: Route.ComponentProps) {
  const [params] = useSearchParams();
  const errors: FieldErrors = actionData?.errors ?? {};
  const submitting = useNavigation().state === "submitting";
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6 sm:p-8">
      <h1 className="text-2xl font-bold">Вход</h1>
      {loaderData.notice && <Alert tone="success">{loaderData.notice}</Alert>}
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}
      <Form method="post" className="space-y-4" noValidate>
        <input type="hidden" name="next" value={params.get("next") ?? ""} />
        <Field label="Email" error={errors.email}>
          {(p) => <Input {...p} name="email" type="email" autoComplete="email" defaultValue={actionData?.email} required />}
        </Field>
        <Field label="Пароль" error={errors.password}>
          {(p) => <Input {...p} name="password" type="password" autoComplete="current-password" required />}
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          Войти
        </Button>
      </Form>
      <div className="flex justify-between text-sm">
        <Link to="/register" className="text-brand-600 hover:underline">Регистрация</Link>
        <Link to="/reset-password" className="text-muted hover:text-ink">Забыли пароль?</Link>
      </div>
    </Card>
  );
}
