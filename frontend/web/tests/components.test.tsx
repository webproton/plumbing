import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { createRoutesStub } from "react-router";
import { describe, expect, it } from "vitest";

import { Pagination } from "~/components/Pagination";
import { Price } from "~/components/Price";
import { QuantityStepper } from "~/components/QuantityStepper";

/** Рендер внутри маршрутизатора (компоненты берут язык из данных root) */
function renderInRouter(ui: React.ReactNode, lang: "uk" | "ru" = "uk") {
  const Stub = createRoutesStub([{ id: "root", path: "/", loader: () => ({ lang }), Component: () => ui }]);
  return render(<Stub />);
}

describe("Price", () => {
  it("shows old price only when it is higher, «from» in page language", async () => {
    renderInRouter(<Price value="900" original="1000" from />);
    expect(await screen.findByText(/від/)).toBeInTheDocument();
    expect(screen.getByText(/1\s000/)).toHaveClass("line-through");
  });

  it("uses Russian on /ru", async () => {
    renderInRouter(<Price value="900" original="900" from />, "ru");
    expect(await screen.findByText(/от/)).toBeInTheDocument();
    expect(document.querySelector(".line-through")).toBeNull();
  });
});

describe("QuantityStepper", () => {
  it("respects min 1 and max", async () => {
    function Wrapper() {
      const [v, setV] = useState(1);
      return <QuantityStepper value={v} onChange={setV} max={2} />;
    }
    renderInRouter(<Wrapper />);
    const input = await screen.findByLabelText("Кількість");
    expect(screen.getByLabelText("Зменшити")).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Збільшити"));
    expect(input).toHaveValue(2);
    expect(screen.getByLabelText("Збільшити")).toBeDisabled();
  });
});

describe("Pagination", () => {
  it("keeps filters in links and marks current page", async () => {
    const Stub = createRoutesStub([
      { id: "root", path: "/catalog", loader: () => ({ lang: "uk" }), Component: () => <Pagination page={2} pages={5} /> },
    ]);
    render(<Stub initialEntries={["/catalog?category=krany&page=2"]} />);
    const current = await screen.findByRole("link", { current: "page" });
    expect(current).toHaveTextContent("2");
    expect(screen.getByRole("link", { name: "1" })).toHaveAttribute("href", "/catalog?category=krany");
    expect(screen.getByRole("link", { name: "5" })).toHaveAttribute("href", "/catalog?category=krany&page=5");
  });
});
