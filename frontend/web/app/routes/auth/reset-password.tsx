import { data, Form, useNavigation } from "react-router";
import { z } from "zod";

import { Alert, Button, Card, Field, Input } from "~/components/ui";
import { langFromRequest, makeT, tFromMatches } from "~/i18n";
import { useT } from "~/i18n/react";
import { apiContext } from "~/lib/context.server";

import type { Route } from "./+types/reset-password";

export const meta: Route.MetaFunction = ({ matches }) => [
  { title: tFromMatches(matches)("auth.reset.title") },
  { name: "robots", content: "noindex" },
];

export async function action({ request, context }: Route.ActionArgs) {
  const email = String((await request.formData()).get("email") ?? "").trim();
  if (!z.email().safeParse(email).success) return data({ sent: false, error: makeT(langFromRequest(request))("v.email") }, { status: 400 });
  // ответ одинаковый, существует адрес или нет — чтобы нельзя было перебирать email клиентов
  await context.get(apiContext).post("/dj-rest-auth/password/reset/", { email }, { auth: false }).catch(() => undefined);
  return { sent: true, error: null };
}

export default function ResetPassword({ actionData }: Route.ComponentProps) {
  const submitting = useNavigation().state === "submitting";
  const t = useT();
  return (
    <Card className="mx-auto max-w-md space-y-5 p-6 sm:p-8">
      <h1 className="text-2xl font-bold">{t("auth.reset.title")}</h1>
      {actionData?.sent ? (
        <Alert tone="success">{t("auth.reset.sent")}</Alert>
      ) : (
        <Form method="post" className="space-y-4" noValidate>
          <Field label={t("auth.email")} error={actionData?.error ?? undefined}>
            {(p) => <Input {...p} name="email" type="email" autoComplete="email" />}
          </Field>
          <Button type="submit" className="w-full" loading={submitting}>
            {t("auth.reset.submit")}
          </Button>
        </Form>
      )}
    </Card>
  );
}
