import { data } from "react-router";

import { langFromRequest, makeT } from "~/i18n";
import { ApiError } from "~/lib/api.server";
import { apiContext } from "~/lib/context.server";
import { formObject, schemas, zodErrors } from "~/lib/validation";

import type { Route } from "./+types/callback";

/** Заявка «перезвоните мне» (вызывается fetcher'ом из CallbackForm) */
export async function action({ request, context }: Route.ActionArgs) {
  const t = makeT(langFromRequest(request));
  const parsed = schemas(t).callback.safeParse(formObject(await request.formData()));
  if (!parsed.success) return data({ ok: false, error: zodErrors(parsed.error).phone }, { status: 400 });
  try {
    await context.get(apiContext).post("/callback/request/", { phone: parsed.data.phone });
    return { ok: true, error: null };
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    const error = e.status === 429 ? t("callback.tooMany") : t("callback.failed");
    return data({ ok: false, error }, { status: 400 });
  }
}
