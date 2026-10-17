import { CheckCircle2 } from "lucide-react";

import { ButtonLink } from "~/components/ui";
import { useRootData } from "~/root";

import type { Route } from "./+types/order-success";

export const meta: Route.MetaFunction = () => [{ title: "Заказ принят" }, { name: "robots", content: "noindex" }];

export default function OrderSuccess({ params }: Route.ComponentProps) {
  const user = useRootData()?.user;
  return (
    <div className="mx-auto max-w-lg space-y-5 py-10 text-center">
      <CheckCircle2 className="mx-auto size-16 text-success" aria-hidden />
      <h1 className="text-3xl font-bold">Заказ №{params.id} принят</h1>
      <p className="text-muted">
        Товар зарезервирован за вами. Менеджер свяжется с вами в рабочее время, чтобы подтвердить заказ и
        отправить реквизиты для оплаты.
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        {user && <ButtonLink to={`/account/orders/${params.id}`} variant="secondary">Мой заказ</ButtonLink>}
        <ButtonLink to="/catalog">Продолжить покупки</ButtonLink>
      </div>
    </div>
  );
}
