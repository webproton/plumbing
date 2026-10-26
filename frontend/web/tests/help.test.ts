import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { HELP } from "~/components/seller/help-content";

const routesDir = join(__dirname, "..", "app", "routes", "seller");

describe("seller help", () => {
  it("has the same sections in both languages", () => {
    const ids = (lang: "uk" | "ru") => HELP[lang].sections.map((s) => s.id);
    expect(ids("ru")).toEqual(ids("uk"));
    expect(new Set(ids("uk")).size).toBe(ids("uk").length);
    expect(HELP.ru.quickStart.map((s) => s.to)).toEqual(HELP.uk.quickStart.map((s) => s.to));
    expect(HELP.ru.faq).toHaveLength(HELP.uk.faq.length);
  });

  it("every «how it works» link on a page points to an existing section", () => {
    const ids = new Set(HELP.uk.sections.map((s) => s.id));
    const used = readdirSync(routesDir)
      .filter((f) => f.endsWith(".tsx"))
      .flatMap((f) => [
        ...readFileSync(join(routesDir, f), "utf8").matchAll(/<PageTitle[^>]*\bhelp="([\w-]+)"/g),
      ])
      .map((m) => m[1]);
    expect(used.length).toBeGreaterThan(5);
    for (const id of used) expect(ids, `/seller/help#${id}`).toContain(id);
  });
});
