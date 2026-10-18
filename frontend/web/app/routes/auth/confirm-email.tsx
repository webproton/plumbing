import { MailCheck, MailX } from "lucide-react";

import { ButtonLink, EmptyState } from "~/components/ui";
import { langFromRequest, makeT } from "~/i18n";
import { useT } from "~/i18n/react";
import { localRedirect } from "~/i18n/server";
import { apiContext } from "~/lib/context.server";
import { sessionContext } from "~/lib/session.server";

import type { Route } from "./+types/confirm-email";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  try {
    await context.get(apiContext).post("/dj-rest-auth/registration/verify-email/", { key: params.key }, { auth: false });
  } catch {
    return { ok: false };
  }
  context.get(sessionContext).flash("notice", makeT(langFromRequest(request))("auth.confirm.okNotice"));
  throw localRedirect(request, "/login");
}

export default function ConfirmEmail({ loaderData }: Route.ComponentProps) {
  const t = useT();
  return loaderData.ok ? (
    <EmptyState icon={MailCheck} title={t("auth.confirm.ok")} />
  ) : (
    <EmptyState icon={MailX} title={t("auth.confirm.bad")}>
      <p className="mb-4">{t("auth.confirm.badText")}</p>
      <ButtonLink to="/login">{t("auth.login.submit")}</ButtonLink>
    </EmptyState>
  );
}
