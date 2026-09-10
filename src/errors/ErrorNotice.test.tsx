// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { invoke as nativeInvoke } from "@tauri-apps/api/core";
import { ErrorNotice } from "./ErrorNotice";
import { invoke } from "./invoke";
import { errorMessages } from "./messages";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it.each(Object.keys(errorMessages) as (keyof typeof errorMessages)[])("renders safe mapping for %s without retrying", async (code) => {
  vi.mocked(nativeInvoke).mockRejectedValue(JSON.stringify({ code, retryable: true, message: "SECRET", details: "STACKTRACE", user_message: "SECRET" }));
  render(<ErrorNotice />);
  await act(async () => {
    await expect(invoke("sessions_send")).rejects.toEqual(errorMessages[code]);
  });
  expect(screen.getByRole(code === "RUN_CANCELLED" ? "status" : "alert")).toHaveTextContent(errorMessages[code]);
  expect(screen.queryByText(/SECRET|STACKTRACE/)).not.toBeInTheDocument();
  expect(nativeInvoke).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "关闭提示" }));
  expect(screen.queryByLabelText("最近一次操作提示")).not.toBeInTheDocument();
});
it("does not leak unknown raw transport failures", async () => {
  vi.mocked(nativeInvoke).mockRejectedValue("SECRET remote error");
  render(<ErrorNotice />);
  await expect(invoke("todos_list")).rejects.toThrow("Desktop request failed");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
