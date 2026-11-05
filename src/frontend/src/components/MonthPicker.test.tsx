import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as mod from "./MonthPicker";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MonthPicker: any = (mod as any).MonthPicker ?? (mod as any).default;

afterEach(cleanup);

function setup(value = "2026-10", max?: string) {
  const onChange = vi.fn();
  const user = userEvent.setup();
  render(<MonthPicker value={value} onChange={onChange} max={max} />);
  return { onChange, user };
}

const prev = () => screen.getByRole("button", { name: "Poprzedni miesiąc" });
const next = () => screen.getByRole("button", { name: "Następny miesiąc" });
const open = () => screen.getByRole("button", { name: "Wybierz miesiąc" });

describe("MonthPicker", () => {
  it("wyświetla polską nazwę w mianowniku", () => {
    setup();
    expect(open().textContent).toMatch(/październik 2026/i);
  });

  it("strzałki zmieniają miesiąc", async () => {
    const { onChange, user } = setup("2026-10");
    await user.click(prev());
    expect(onChange).toHaveBeenLastCalledWith("2026-09");
    await user.click(next());
    expect(onChange).toHaveBeenLastCalledWith("2026-11");
  });

  it("granica roku: styczeń -> grudzień poprzedniego", async () => {
    const { onChange, user } = setup("2026-01");
    await user.click(prev());
    expect(onChange).toHaveBeenCalledWith("2025-12");
  });

  it("granica roku: grudzień -> styczeń następnego", async () => {
    const { onChange, user } = setup("2026-12");
    await user.click(next());
    expect(onChange).toHaveBeenCalledWith("2027-01");
  });

  it("następny miesiąc wyłączony przy max", async () => {
    const { onChange, user } = setup("2026-10", "2026-10");
    expect((next() as HTMLButtonElement).disabled).toBe(true);
    await user.click(next());
    expect(onChange).not.toHaveBeenCalled();
    expect((prev() as HTMLButtonElement).disabled).toBe(false);
  });

  it("popover otwiera się z siatką 12 miesięcy", async () => {
    const { user } = setup();
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(open());
    const dialog = screen.getByRole("dialog");
    for (const m of ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]) {
      expect(within(dialog).getByText(m)).toBeTruthy();
    }
    expect(dialog.textContent).toContain("2026");
  });

  it("bieżący miesiąc ma aria-pressed", async () => {
    const { user } = setup("2026-10");
    await user.click(open());
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("paź").closest("button")!.getAttribute("aria-pressed")).toBe("true");
    expect(within(dialog).getByText("lis").closest("button")!.getAttribute("aria-pressed")).not.toBe("true");
  });

  it("wybór miesiąca woła onChange i zamyka popover", async () => {
    const { onChange, user } = setup("2026-10");
    await user.click(open());
    await user.click(within(screen.getByRole("dialog")).getByText("mar"));
    expect(onChange).toHaveBeenCalledWith("2026-03");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Escape zamyka popover", async () => {
    const { user } = setup();
    await user.click(open());
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("kliknięcie poza popoverem zamyka go", async () => {
    const { user } = setup();
    await user.click(open());
    await user.click(document.body);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("zmiana roku w popoverze", async () => {
    const { onChange, user } = setup("2026-10");
    await user.click(open());
    const dialog = screen.getByRole("dialog");
    const prevYear = within(dialog).getByRole("button", { name: /poprzedni.*rok|rok.*poprzedni/i });
    await user.click(prevYear);
    expect(dialog.textContent).toContain("2025");
    await user.click(within(dialog).getByText("lut"));
    expect(onChange).toHaveBeenCalledWith("2025-02");
  });

  it("miesiące po max są wyłączone w popoverze", async () => {
    const { onChange, user } = setup("2026-10", "2026-10");
    await user.click(open());
    const dialog = screen.getByRole("dialog");
    const lis = within(dialog).getByText("lis").closest("button") as HTMLButtonElement;
    expect(lis.disabled).toBe(true);
    await user.click(lis);
    expect(onChange).not.toHaveBeenCalled();
    expect((within(dialog).getByText("wrz").closest("button") as HTMLButtonElement).disabled).toBe(false);
  });
});
