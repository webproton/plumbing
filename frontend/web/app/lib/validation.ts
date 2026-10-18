import { z } from "zod";

import { makeT, type TFunction } from "~/i18n";

import type { FieldErrors } from "./types";

/** +380XXXXXXXXX или 0XXXXXXXXX (пробелы, скобки и дефисы допустимы) → +380XXXXXXXXX */
export function normalizePhone(raw: string): string | null {
  const digits = raw.replace(/\D/g, "");
  if (digits.length === 10 && digits.startsWith("0")) return `+38${digits}`;
  if (digits.length === 12 && digits.startsWith("380")) return `+${digits}`;
  return null;
}

export function schemas(t: TFunction) {
  const phone = z
    .string()
    .trim()
    .transform((v, ctx) => {
      const normalized = normalizePhone(v);
      if (!normalized) {
        ctx.addIssue({ code: "custom", message: t("v.phone") });
        return z.NEVER;
      }
      return normalized;
    });

  const personName = z
    .string()
    .trim()
    .min(2, t("v.name"))
    .regex(/^[\p{L}]+(?:[ '’-][\p{L}]+)*$/u, t("v.nameChars"));

  const checkout = z
    .object({
      first_name: personName,
      last_name: personName,
      phone_number: phone,
      email: z.union([z.literal(""), z.email(t("v.email"))]),
      delivery: z.enum(["nova_poshta", "pickup"]),
      city: z.string().trim(),
      department_number: z.string().trim(),
      comment: z
        .string()
        .trim()
        .max(500, t("v.max500"))
        .refine((v) => !/https?:\/\//i.test(v), t("v.noLinks")),
      payment_type: z.enum(["full", "partial"]),
    })
    .superRefine((data, ctx) => {
      if (data.delivery === "nova_poshta") {
        if (!data.city) ctx.addIssue({ code: "custom", path: ["city"], message: t("v.city") });
        if (!data.department_number)
          ctx.addIssue({ code: "custom", path: ["department_number"], message: t("v.department") });
      }
    });

  const login = z.object({
    email: z.email(t("v.email")),
    password: z.string().min(1, t("v.password")),
  });

  const register = z
    .object({
      email: z.email(t("v.email")),
      password1: z.string().min(8, t("v.passwordMin")),
      password2: z.string(),
    })
    .refine((d) => d.password1 === d.password2, { path: ["password2"], message: t("v.passwordMismatch") });

  const profile = z.object({
    first_name: z.string().trim().max(30),
    last_name: z.string().trim().max(30),
    middle_name: z.string().trim().max(30),
    phone_number: z.union([z.literal(""), phone]),
    city: z.string().trim().max(100),
    address: z.string().trim().max(255),
  });

  const callback = z.object({ phone });

  return { checkout, login, register, profile, callback };
}

/** Ошибки zod → {поле: "первое сообщение"} */
export function zodErrors(error: z.ZodError): FieldErrors {
  const out: FieldErrors = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0] ?? "form");
    out[key] ??= issue.message;
  }
  return out;
}

export function formObject(form: FormData): Record<string, string> {
  return Object.fromEntries([...form.entries()].map(([k, v]) => [k, typeof v === "string" ? v : ""]));
}

/** Схемы с украинскими сообщениями (по умолчанию; для тестов и мест без запроса) */
export const defaultSchemas = schemas(makeT("uk"));
