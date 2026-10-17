import { PhoneCall } from "lucide-react";
import { useFetcher } from "react-router";

import { Button, Input } from "./ui";

export function CallbackForm() {
  const fetcher = useFetcher<{ ok: boolean; error: string | null }>();
  if (fetcher.data?.ok) {
    return <p className="font-medium text-success">Спасибо! Перезвоним в течение рабочего дня.</p>;
  }
  return (
    <fetcher.Form method="post" action="/callback" className="flex flex-col gap-2 sm:flex-row">
      <Input name="phone" type="tel" inputMode="tel" placeholder="+380 50 123 45 67" aria-label="Телефон" required />
      <Button type="submit" loading={fetcher.state !== "idle"} className="shrink-0">
        <PhoneCall className="size-4" aria-hidden /> Перезвоните мне
      </Button>
      {fetcher.data?.error && <p className="text-sm text-danger sm:self-center">{fetcher.data.error}</p>}
    </fetcher.Form>
  );
}
