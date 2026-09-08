// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RunControl } from "./RunControl";
import type { RunEvent, SessionApi } from "./types";

afterEach(cleanup);

it("uses the live run ID, ignores an old finish and prevents duplicate cancel", async () => {
  let handler!: (event: RunEvent) => void;
  const stop = vi.fn();
  const api = {
    listenRuns: vi.fn(async (callback) => { handler = callback; return stop; }),
    cancel: vi.fn().mockResolvedValue(true),
  } as unknown as SessionApi;
  const view = render(<RunControl api={api} executing />);
  await act(async () => {});
  act(() => handler({ event: "run.started", session_id: "s", run_id: "new" }));
  act(() => handler({ event: "run.finished", session_id: "s", run_id: "old" }));
  const button = screen.getByText("停止执行");
  fireEvent.click(button);
  fireEvent.click(button);
  await act(async () => {});
  expect(api.cancel).toHaveBeenCalledTimes(1);
  expect(api.cancel).toHaveBeenCalledWith("s", "new");
  act(() => handler({ event: "run.finished", session_id: "s", run_id: "new" }));
  expect(screen.queryByText("停止执行")).toBeNull();
  view.unmount();
  expect(stop).toHaveBeenCalledTimes(1);
});
