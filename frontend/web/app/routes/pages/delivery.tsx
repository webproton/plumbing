import { CreditCard, PackageOpen, Truck, Undo2 } from "lucide-react";

import { Card, PageTitle } from "~/components/ui";

import type { Route } from "./+types/delivery";

export const meta: Route.MetaFunction = () => [
  { title: "Доставка и оплата" },
  { name: "description", content: "Доставка Новой Почтой по Украине, самовывоз, оплата и возврат товара." },
];

const BLOCKS = [
  { icon: Truck, title: "Новая Почта", text: "Отправляем в день подтверждения заказа (в рабочие дни). Срок — 1–3 дня, стоимость — по тарифам перевозчика." },
  { icon: PackageOpen, title: "Самовывоз", text: "Заберите заказ со склада после звонка менеджера — товар будет собран и проверен." },
  { icon: CreditCard, title: "Оплата", text: "Полная оплата или предоплата 50 % по реквизитам, которые пришлёт менеджер после подтверждения." },
  { icon: Undo2, title: "Возврат", text: "Товар надлежащего качества можно вернуть в течение 14 дней, если он не был в использовании." },
];

export default function Delivery() {
  return (
    <div>
      <PageTitle>Доставка и оплата</PageTitle>
      <div className="grid gap-4 sm:grid-cols-2">
        {BLOCKS.map(({ icon: Icon, title, text }) => (
          <Card key={title} className="flex gap-4 p-5">
            <Icon className="size-8 shrink-0 text-brand-600" aria-hidden />
            <div>
              <h2 className="font-semibold">{title}</h2>
              <p className="text-muted">{text}</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
