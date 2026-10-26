import { describe, expect, it } from "vitest";

import { brandDiscountsText, parseBrandDiscounts } from "~/lib/discounts";

describe("brand discounts", () => {
  it("parses one brand per line with comma or dot", () => {
    expect(parseBrandDiscounts("KOER 17,7\nGrohe: 25 %\n\n  Hansgrohe — 20.5  ")).toEqual({
      KOER: "17.7",
      Grohe: "25",
      Hansgrohe: "20.5",
    });
  });

  it("keeps multi-word brands and passes unclear lines to the server", () => {
    expect(parseBrandDiscounts("Imprese Lesná 18\nбез відсотка")).toEqual({
      "Imprese Lesná": "18",
      "без відсотка": "?",
    });
  });

  it("renders saved discounts back as lines", () => {
    expect(brandDiscountsText({ KOER: 17.7, Grohe: 25 })).toBe("KOER 17.7\nGrohe 25");
    expect(brandDiscountsText(undefined)).toBe("");
  });
});
