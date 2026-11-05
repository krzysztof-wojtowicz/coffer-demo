import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as mod from "./Button";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const Button: any = (mod as any).Button ?? (mod as any).default;

afterEach(cleanup);

describe("Button", () => {
  it("woła onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Zapisz</Button>);
    await userEvent.click(screen.getByRole("button", { name: /Zapisz/ }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("loading blokuje onClick", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Zapisz
      </Button>,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("przyjmuje className", () => {
    render(<Button className="moja-klasa">X</Button>);
    expect(screen.getByRole("button").className).toContain("moja-klasa");
  });
});
