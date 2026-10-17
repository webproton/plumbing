import { MailCheck, MailX } from "lucide-react";
import { redirect } from "react-router";

import { ButtonLink, EmptyState } from "~/components/ui";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";

import type { Route } from "./+types/confirm-email";

export async function loader({ params, context }: Route.LoaderArgs) {
  try {
    await context.get(apiContext).post("/dj-rest-auth/registration/verify-email/", { key: params.key }, { auth: false });
  } catch {
    return { ok: false };
  }
  context.get(sessionContext).flash("notice", "Email подтверждён — теперь можно войти.");
  throw redirect("/login");
}

export default function ConfirmEmail({ loaderData }: Route.ComponentProps) {
  return loaderData.ok ? (
    <EmptyState icon={MailCheck} title="Email подтверждён" />
  ) : (
    <EmptyState icon={MailX} title="Ссылка недействительна">
      <p className="mb-4">Возможно, она устарела или уже использована.</p>
      <ButtonLink to="/login">Войти</ButtonLink>
    </EmptyState>
  );
}
