import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CATEGORIES } from "@/lib/categories";
import CategoryFilter from "./CategoryFilter";

describe("CategoryFilter", () => {
  it("renders an 'All' button plus every category", () => {
    render(<CategoryFilter selected={null} onSelect={() => {}} />);

    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    for (const category of CATEGORIES) {
      expect(screen.getByRole("button", { name: category })).toBeInTheDocument();
    }
  });

  it("calls onSelect with the clicked category", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<CategoryFilter selected={null} onSelect={onSelect} />);

    await user.click(screen.getByRole("button", { name: "wholesome" }));

    expect(onSelect).toHaveBeenCalledWith("wholesome");
  });

  it("calls onSelect with null when 'All' is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<CategoryFilter selected="dark" onSelect={onSelect} />);

    await user.click(screen.getByRole("button", { name: "All" }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("marks the selected category as active", () => {
    render(<CategoryFilter selected="surreal" onSelect={() => {}} />);

    const activeButton = screen.getByRole("button", { name: "surreal" });
    const allButton = screen.getByRole("button", { name: "All" });

    expect(activeButton.className).not.toBe(allButton.className);
  });
});
