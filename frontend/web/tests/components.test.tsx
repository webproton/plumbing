import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { createRoutesStub } from "react-router";
import { describe, expect, it } from "vitest";

import { Pagination } from "~/components/Pagination";
import { Price } from "~/components/Price";
import { QuantityStepper } from "~/components/QuantityStepper";

describe("Price", () => {
  it("shows old price only when it is higher", () => {
    const { rerender } = render(<Price value="900" original="1000" from />);
    expect(screen.getByText(/от/)).toBeInTheDocument();
    expect(screen.getByText(/1\s000/)).toHaveClass("line-through");
    rerender(<Price value="900" original="900" />);
    expect(document.querySelector(".line-through")).toBeNull();
  });
});

describe("QuantityStepper", () => {
  it("respects min 1 and max", async () => {
    function Wrapper() {
      const [v, setV] = useState(1);
      return <QuantityStepper value={v} onChange={setV} max={2} />;
    }
    render(<Wrapper />);
    const input = screen.getByLabelText("Количество");
    expect(screen.getByLabelText("Уменьшить")).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Увеличить"));
    expect(input).toHaveValue(2);
    expect(screen.getByLabelText("Увеличить")).toBeDisabled();
  });
});

describe("Pagination", () => {
  it("keeps filters in links and marks current page", async () => {
    const Stub = createRoutesStub([{ path: "/catalog", Component: () => <Pagination page={2} pages={5} /> }]);
    render(<Stub initialEntries={["/catalog?category=krany&page=2"]} />);
    const current = await screen.findByRole("link", { current: "page" });
    expect(current).toHaveTextContent("2");
    expect(screen.getByRole("link", { name: "1" })).toHaveAttribute("href", "/catalog?category=krany");
    expect(screen.getByRole("link", { name: "5" })).toHaveAttribute("href", "/catalog?category=krany&page=5");
  });
});
