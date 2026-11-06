import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Layout } from "./Layout";

beforeEach(() => {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }) as unknown as typeof window.matchMedia;
});
afterEach(cleanup);

describe("Layout (tester)", () => {
  it("renders the theme radiogroup 'Motyw' for a logged-in view", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <Routes>
            <Route element={<Layout email="a@b.pl" />}>
              <Route index element={<p>treść</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const group = screen.getByRole("radiogroup", { name: "Motyw" });
    expect(group).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("treść")).toBeTruthy();
  });
});
