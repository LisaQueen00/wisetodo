// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DesktopControls } from "./DesktopControls";
import type { DesktopApi } from "./api";

afterEach(cleanup);
function service(abnormal = false): DesktopApi {
  const state = { pinned: true, autostart: false, abnormal_exit: abnormal, tray_available: true };
  return {
    status: vi.fn(async () => ({ ...state })),
    pin: vi.fn(async (value) => { state.pinned = value; }),
    autostart: vi.fn(async (value) => { state.autostart = value; }),
    acknowledge: vi.fn(async () => { state.abnormal_exit = false; }),
    restart: vi.fn(async () => {}),
  };
}
it("reads settings without enabling startup and saves explicit choices", async () => {
  const api = service();
  render(<DesktopControls api={api} />);
  const pin = screen.getByRole("button", { name: "窗口置顶" });
  await waitFor(() => expect(pin).toBeEnabled());
  expect(api.autostart).not.toHaveBeenCalled();
  fireEvent.click(pin);
  await waitFor(() => expect(pin).toHaveAttribute("aria-pressed", "false"));
  fireEvent.click(screen.getByRole("checkbox", { name: "开机启动" }));
  await waitFor(() => expect(api.autostart).toHaveBeenCalledWith(true));
});
it("does not restart on abnormal startup without confirmation", async () => {
  const api = service(true);
  render(<DesktopControls api={api} />);
  await screen.findByText(/上次可能未正常退出/);
  expect(api.restart).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "继续使用" }));
  await waitFor(() => expect(screen.queryByText(/上次可能未正常退出/)).not.toBeInTheDocument());
  expect(api.acknowledge).toHaveBeenCalledOnce();
});
it("shows safe errors and retains the previous pin state", async () => {
  const api = service();
  api.pin = vi.fn().mockRejectedValue(new Error("private detail"));
  render(<DesktopControls api={api} />);
  const pin = screen.getByRole("button", { name: "窗口置顶" });
  await waitFor(() => expect(pin).toBeEnabled());
  fireEvent.click(pin);
  await screen.findByText(/桌面设置操作失败/);
  expect(pin).toHaveAttribute("aria-pressed", "true");
  expect(screen.queryByText("private detail")).not.toBeInTheDocument();
});
it("keeps pinning usable when startup integration or the tray is unavailable", async () => {
  const api = service();
  api.status = vi.fn(async () => ({ pinned: true, autostart: null, abnormal_exit: false, tray_available: false }));
  render(<DesktopControls api={api} />);
  await screen.findByText("托盘不可用，关闭窗口将退出应用。");
  expect(screen.getByRole("button", { name: "窗口置顶" })).toBeEnabled();
  expect(screen.getByRole("checkbox", { name: "开机启动" })).toBeDisabled();
});
