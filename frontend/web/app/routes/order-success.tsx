import { CheckCircle2 } from "lucide-react";

import { ButtonLink } from "~/components/ui";
import { makeT } from "~/i18n";
import { useT } from "~/i18n/react";
import { useRootData } from "~/root";

import type { Route } from "./+types/order-success";

export const meta: Route.MetaFunction = ({ matches }) => {
  const lang = (matches[0]?.loaderData as { lang?: "uk" | "ru" } | undefined)?.lang ?? "uk";
  return [{ title: makeT(lang)("order.accepted.meta") }, { name: "robots", content: "noindex" }];
};

export default function OrderSuccess({ params }: Route.ComponentProps) {
  const user = useRootData()?.user;
  const t = useT();
  return (
    <div className="mx-auto max-w-lg space-y-5 py-10 text-center">
      <CheckCircle2 className="mx-auto size-16 text-success" aria-hidden />
      <h1 className="text-3xl font-bold">{t("order.accepted.title", { id: params.id })}</h1>
      <p className="text-muted">{t("order.accepted.text")}</p>
      <div className="flex flex-wrap justify-center gap-3">
        {user && (
          <ButtonLink to={`/account/orders/${params.id}`} variant="secondary">
            {t("order.accepted.my")}
          </ButtonLink>
        )}
        <ButtonLink to="/catalog">{t("cart.continue")}</ButtonLink>
      </div>
    </div>
  );
}
