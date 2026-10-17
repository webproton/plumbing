import { Mail, MessageCircle, Phone } from "lucide-react";

import { CallbackForm } from "~/components/CallbackForm";
import { Card, PageTitle } from "~/components/ui";
import { useRootData } from "~/root";

import type { Route } from "./+types/contacts";

export const meta: Route.MetaFunction = () => [{ title: "Контакты" }];

export default function Contacts() {
  const s = useRootData()?.settings;
  return (
    <div className="max-w-2xl space-y-6">
      <PageTitle subtitle="Пн–Пт 9:00–18:00">Контакты</PageTitle>
      <Card className="space-y-3 p-5">
        {s?.phone && (
          <a href={`tel:${s.phone}`} className="flex items-center gap-3 text-lg font-medium">
            <Phone className="size-5 text-brand-600" aria-hidden /> {s.phone}
          </a>
        )}
        {s?.email && (
          <a href={`mailto:${s.email}`} className="flex items-center gap-3">
            <Mail className="size-5 text-brand-600" aria-hidden /> {s.email}
          </a>
        )}
        {s?.telegram && (
          <p className="flex items-center gap-3">
            <MessageCircle className="size-5 text-brand-600" aria-hidden /> Telegram: {s.telegram}
          </p>
        )}
        {!s && <p className="text-muted">Контакты временно недоступны.</p>}
      </Card>
      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">Перезвоним вам</h2>
        <CallbackForm />
      </Card>
    </div>
  );
}
