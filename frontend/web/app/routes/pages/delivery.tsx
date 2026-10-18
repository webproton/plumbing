import { CreditCard, PackageOpen, Truck, Undo2 } from "lucide-react";

import { Card, PageTitle } from "~/components/ui";
import { tFromMatches, type TKey } from "~/i18n";
import { useT } from "~/i18n/react";

import type { Route } from "./+types/delivery";

export const meta: Route.MetaFunction = ({ matches }) => {
  const t = tFromMatches(matches);
  return [{ title: t("page.delivery.title") }, { name: "description", content: t("page.delivery.meta") }];
};

const BLOCKS: { icon: typeof Truck; title: TKey; text: TKey }[] = [
  { icon: Truck, title: "page.delivery.np", text: "page.delivery.npText" },
  { icon: PackageOpen, title: "page.delivery.pickup", text: "page.delivery.pickupText" },
  { icon: CreditCard, title: "page.delivery.payment", text: "page.delivery.paymentText" },
  { icon: Undo2, title: "page.delivery.return", text: "page.delivery.returnText" },
];

export default function Delivery() {
  const t = useT();
  return (
    <div>
      <PageTitle>{t("page.delivery.title")}</PageTitle>
      <div className="grid gap-4 sm:grid-cols-2">
        {BLOCKS.map(({ icon: Icon, title, text }) => (
          <Card key={title} className="flex gap-4 p-5">
            <Icon className="size-8 shrink-0 text-brand-600" aria-hidden />
            <div>
              <h2 className="font-semibold">{t(title)}</h2>
              <p className="text-muted">{t(text)}</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
