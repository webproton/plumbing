import { CheckCircle2 } from "lucide-react";
import { useEffect } from "react";

import { ButtonLink } from "~/components/ui";
import { makeT } from "~/i18n";
import { useT } from "~/i18n/react";
import { trackEvent } from "~/lib/analytics";
import { sessionContext } from "~/lib/session.server";
import { useRootData } from "~/root";

import type { Route } from "./+types/order-success";

export const meta: Route.MetaFunction = ({ matches }) => {
  const lang = (matches[0]?.loaderData as { lang?: "uk" | "ru" } | undefined)?.lang ?? "uk";
  return [{ title: makeT(lang)("order.accepted.meta") }, { name: "robots", content: "noindex" }];
};

/** Данные заказа для события «покупка» (одноразово, из сессии после оформления) */
export function loader({ context }: Route.LoaderArgs) {
  return { purchase: context.get(sessionContext).get("purchase") ?? null };
}

export default function OrderSuccess({ params, loaderData }: Route.ComponentProps) {
  const user = useRootData()?.user;
  const t = useT();
  const purchase = loaderData.purchase;
  useEffect(() => {
    if (purchase) trackEvent("purchase", { orderId: purchase.id, value: purchase.value, items: purchase.items });
  }, [purchase]);
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
