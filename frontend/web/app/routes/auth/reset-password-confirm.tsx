import { data, Form, redirect, useNavigation, useSearchParams } from "react-router";

import { Alert, Button, Card, Field, Input } from "~/components/ui";
import { ApiError } from "~/lib/api.server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";
import type { FieldErrors } from "~/lib/types";
import { formObject } from "~/lib/validation";

import type { Route } from "./+types/reset-password-confirm";

export const meta: Route.MetaFunction = () => [{ title: "Новый пароль" }, { name: "robots", content: "noindex" }];

export async function action({ request, context }: Route.ActionArgs) {
  const v = formObject(await request.formData());
  if (v.new_password1 !== v.new_password2) {
    return data({ errors: { new_password2: "Пароли не совпадают" } as FieldErrors }, { status: 400 });
  }
  try {
    await context.get(apiContext).post("/dj-rest-auth/password/reset/confirm/", v, { auth: false });
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const errors = e.fieldErrors;
    if (errors.token || errors.uid) errors.form = "Ссылка устарела. Запросите восстановление пароля ещё раз.";
    return data({ errors }, { status: 400 });
  }
  context.get(sessionContext).flash("notice", "Пароль изменён — войдите с новым паролем.");
  return redirect("/login");
}

export default function ResetPasswordConfirm({ actionData }: Route.ComponentProps) {
  const [params] = useSearchParams();
  const errors: FieldErrors = actionData?.errors ?? {};
  const submitting = useNavigation().state === "submitting";
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6 sm:p-8">
      <h1 className="text-2xl font-bold">Новый пароль</h1>
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}
      <Form method="post" className="space-y-4" noValidate>
        <input type="hidden" name="uid" value={params.get("uid") ?? ""} />
        <input type="hidden" name="token" value={params.get("token") ?? ""} />
        <Field label="Новый пароль" error={errors.new_password1}>
          {(p) => <Input {...p} name="new_password1" type="password" autoComplete="new-password" />}
        </Field>
        <Field label="Повторите пароль" error={errors.new_password2}>
          {(p) => <Input {...p} name="new_password2" type="password" autoComplete="new-password" />}
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          Сохранить пароль
        </Button>
      </Form>
    </Card>
  );
}
