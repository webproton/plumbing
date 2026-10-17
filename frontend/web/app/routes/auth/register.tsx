import { MailCheck } from "lucide-react";
import { data, Form, Link, redirect, useNavigation } from "react-router";

import { Alert, Button, Card, EmptyState, Field, Input } from "~/components/ui";
import { ApiError } from "~/lib/api.server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";
import type { FieldErrors } from "~/lib/types";
import { formObject, registerSchema, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/register";

export const meta: Route.MetaFunction = () => [{ title: "Регистрация" }, { name: "robots", content: "noindex" }];

export function loader({ context }: Route.LoaderArgs) {
  if (context.get(sessionContext).has("user")) throw redirect("/account");
  return null;
}

export async function action({ request, context }: Route.ActionArgs) {
  const values = formObject(await request.formData());
  const parsed = registerSchema.safeParse(values);
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
  if (actionData?.sent) {
    return (
      <EmptyState icon={MailCheck} title="Проверьте почту">
        Мы отправили письмо на <b>{actionData.email}</b>. Перейдите по ссылке из письма, чтобы подтвердить адрес.
      </EmptyState>
    );
  }
  const errors: FieldErrors = actionData?.errors ?? {};
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6 sm:p-8">
      <h1 className="text-2xl font-bold">Регистрация</h1>
      {errors.form && <Alert tone="danger">{errors.form}</Alert>}
      <Form method="post" className="space-y-4" noValidate>
        <Field label="Email" error={errors.email}>
          {(p) => <Input {...p} name="email" type="email" autoComplete="email" defaultValue={actionData?.email} />}
        </Field>
        <Field label="Пароль" error={errors.password1} hint="Не короче 8 символов, не только цифры">
          {(p) => <Input {...p} name="password1" type="password" autoComplete="new-password" />}
        </Field>
        <Field label="Повторите пароль" error={errors.password2}>
          {(p) => <Input {...p} name="password2" type="password" autoComplete="new-password" />}
        </Field>
        <Button type="submit" className="w-full" loading={submitting}>
          Создать аккаунт
        </Button>
      </Form>
      <p className="text-center text-sm text-muted">
        Уже есть аккаунт? <Link to="/login" className="text-brand-600 hover:underline">Войти</Link>
      </p>
    </Card>
  );
}
