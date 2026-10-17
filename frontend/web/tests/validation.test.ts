import { describe, expect, it } from "vitest";

import { checkoutSchema, normalizePhone, registerSchema, zodErrors } from "~/lib/validation";

const base = {
  first_name: "Мар'яна",
  last_name: "Коваль-Петренко",
  phone_number: "050 123 45 67",
  email: "",
  delivery: "nova_poshta",
  city: "Київ",
  department_number: "12",
  comment: "",
  payment_type: "full",
};

describe("normalizePhone", () => {
  it.each([
    ["0501234567", "+380501234567"],
    ["+38 (050) 123-45-67", "+380501234567"],
    ["380501234567", "+380501234567"],
  ])("%s → %s", (raw, expected) => expect(normalizePhone(raw)).toBe(expected));

  it("rejects wrong length", () => expect(normalizePhone("12345")).toBeNull());
});

describe("checkoutSchema", () => {
  it("accepts names with apostrophe and hyphen, normalizes phone", () => {
    const r = checkoutSchema.parse(base);
    expect(r.phone_number).toBe("+380501234567");
  });

  it("requires city and department for Nova Poshta only", () => {
    const np = checkoutSchema.safeParse({ ...base, city: "", department_number: "" });
    expect(np.success).toBe(false);
    if (!np.success) expect(Object.keys(zodErrors(np.error))).toEqual(["city", "department_number"]);
    expect(checkoutSchema.safeParse({ ...base, delivery: "pickup", city: "", department_number: "" }).success).toBe(true);
  });

  it("rejects links in comment and digits in name", () => {
    const r = checkoutSchema.safeParse({ ...base, first_name: "Иван2", comment: "см. https://spam" });
    expect(r.success).toBe(false);
    if (!r.success) expect(zodErrors(r.error)).toMatchObject({ first_name: expect.any(String), comment: expect.any(String) });
  });
});

describe("registerSchema", () => {
  it("checks password confirmation", () => {
    const r = registerSchema.safeParse({ email: "a@ukr.net", password1: "Secret123!", password2: "other" });
    expect(r.success).toBe(false);
    if (!r.success) expect(zodErrors(r.error).password2).toBe("Пароли не совпадают");
  });
});
