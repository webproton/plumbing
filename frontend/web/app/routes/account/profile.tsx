import { data, Form, useNavigation } from "react-router";

import { Alert, Button, Card, Field, Input, PageTitle } from "~/components/ui";
import { ApiError } from "~/lib/api.server";
import { requireUser } from "~/lib/auth.server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";
import type { FieldErrors, UserProfile } from "~/lib/types";
import { formObject, profileSchema, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/profile";

export const meta: Route.MetaFunction = () => [{ title: "Профиль" }];

export async function loader({ request, context }: Route.LoaderArgs) {
  requireUser(request, context);
  return { profile: await context.get(apiContext).get<UserProfile>("/dj-rest-auth/profile/") };
}

export async function action({ request, context }: Route.ActionArgs) {
  const user = requireUser(request, context);
  const parsed = profileSchema.safeParse(formObject(await request.formData()));
  if (!parsed.success) return data({ errors: zodErrors(parsed.error), saved: false }, { status: 400 });
  try {
    const profile = await context.get(apiContext).patch<UserProfile>("/dj-rest-auth/profile/", parsed.data);
    const name = [profile.first_name, profile.last_name].filter(Boolean).join(" ");
    context.get(sessionContext).set("user", { ...user, name });
    return { errors: {} as FieldErrors, saved: true };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return data({ errors: e.fieldErrors, saved: false }, { status: 400 });
  }
}

export default function Profile({ loaderData, actionData }: Route.ComponentProps) {
  const p = loaderData.profile;
  const errors: FieldErrors = actionData?.errors ?? {};
  const submitting = useNavigation().state === "submitting";
  return (
    <div>
      <PageTitle subtitle={p.email}>Профиль</PageTitle>
      <Card className="p-5">
        <Form method="post" className="space-y-4" noValidate>
          {actionData?.saved && <Alert tone="success">Изменения сохранены</Alert>}
          {errors.form && <Alert tone="danger">{errors.form}</Alert>}
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Имя" error={errors.first_name}>{(f) => <Input {...f} name="first_name" defaultValue={p.first_name} />}</Field>
            <Field label="Фамилия" error={errors.last_name}>{(f) => <Input {...f} name="last_name" defaultValue={p.last_name} />}</Field>
            <Field label="Отчество" error={errors.middle_name}>{(f) => <Input {...f} name="middle_name" defaultValue={p.middle_name ?? ""} />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Телефон" error={errors.phone_number}>
              {(f) => <Input {...f} name="phone_number" type="tel" defaultValue={p.phone_number ?? ""} placeholder="+380 50 123 45 67" />}
            </Field>
            <Field label="Город" error={errors.city}>{(f) => <Input {...f} name="city" defaultValue={p.city ?? ""} />}</Field>
          </div>
          <Field label="Адрес" error={errors.address}>{(f) => <Input {...f} name="address" defaultValue={p.address ?? ""} />}</Field>
          <Button type="submit" loading={submitting}>Сохранить</Button>
        </Form>
      </Card>
    </div>
  );
}
