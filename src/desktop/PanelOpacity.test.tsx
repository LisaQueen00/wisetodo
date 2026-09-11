// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { validOpacity } from "./usePanelOpacity";

afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });
it("applies background alpha only and retains the preference after remount", () => {
  const first = render(<App />);
  fireEvent.click(screen.getByText("桌面选项"));
  expect(screen.getByRole("slider")).toHaveValue("85");
  fireEvent.change(screen.getByRole("slider"), { target: { value: "65" } });
  expect(screen.getByRole("main").style.getPropertyValue("--panel-alpha")).toBe("0.65");
  expect(screen.getByRole("main").style.opacity).toBe("");
  first.unmount();
  render(<App />);
  fireEvent.click(screen.getByText("桌面选项"));
  expect(screen.getByRole("slider")).toHaveValue("65");
  fireEvent.click(screen.getByText("恢复不透明背景"));
  expect(screen.getByRole("slider")).toHaveValue("100");
});
it("recovers from invalid or inaccessible storage and reports failed saves", () => {
  localStorage.setItem("wisetodo.panel-opacity.v1", "NaN");
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
  render(<App />);
  fireEvent.click(screen.getByText("桌面选项"));
  expect(screen.getByRole("slider")).toHaveValue("85");
  fireEvent.change(screen.getByRole("slider"), { target: { value: "75" } });
  expect(screen.getByRole("alert")).toHaveTextContent("未能保存");
  expect(screen.getByRole("slider")).toHaveValue("75");
});
it("bounds opacity to a usable nonzero range", () => {
  for (const value of [0, 59, 101, NaN, Infinity, 70.1]) expect(validOpacity(value)).toBe(false);
  expect(validOpacity(60)).toBe(true);
  expect(validOpacity(100)).toBe(true);
});
