import { invoke } from "@tauri-apps/api/core";
import { beforeEach, expect, it, vi } from "vitest";
import { desktopSessionApi } from "./desktop";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
const session = { id: "one", label: "阅读", status: "ready", created_at: "date", updated_at: "date", messages: [], tool_events: [] };

it("uses fixed desktop commands for list create get and delete", async () => {
  vi.mocked(invoke).mockResolvedValue({ sessions: [session] });
  expect(await desktopSessionApi.list()).toEqual([session]);
  expect(invoke).toHaveBeenLastCalledWith("sessions_list");
  vi.mocked(invoke).mockResolvedValue({ session });
  expect(await desktopSessionApi.create("阅读")).toEqual(session);
  expect(invoke).toHaveBeenLastCalledWith("sessions_create", { label: "阅读" });
  expect(await desktopSessionApi.get("one")).toEqual(session);
  expect(invoke).toHaveBeenLastCalledWith("sessions_get", { sessionId: "one" });
  expect(await desktopSessionApi.retry("one")).toEqual(session);
  expect(invoke).toHaveBeenLastCalledWith("sessions_retry", { sessionId: "one" });
  expect(await desktopSessionApi.send("one", "message-id", "Hello")).toEqual(session);
  expect(invoke).toHaveBeenLastCalledWith("sessions_send", { sessionId: "one", message: { message_id: "message-id", content: "Hello" } });
  vi.mocked(invoke).mockResolvedValue({ deleted: false });
  expect(await desktopSessionApi.delete("one")).toBe(false);
  expect(invoke).toHaveBeenLastCalledWith("sessions_delete", { sessionId: "one" });
});

it.each([{}, { session: { ...session, id: "wrong" } }, { session: { ...session, messages: [{}] } },
  { session: { ...session, tool_events: [{}] } }, { session: { ...session, status: "unknown" } }])(
  "rejects malformed or mismatched history %j", async (result) => {
    vi.mocked(invoke).mockResolvedValue(result);
    await expect(desktopSessionApi.get("one")).rejects.toThrow();
    await expect(desktopSessionApi.retry("one")).rejects.toThrow();
    await expect(desktopSessionApi.send("one", "id", "Hello")).rejects.toThrow();
  },
);

it("rejects invalid lists and delete acknowledgements and propagates transport failures", async () => {
  vi.mocked(invoke).mockResolvedValue({ sessions: [{}], deleted: "false" });
  await expect(desktopSessionApi.list()).rejects.toThrow();
  await expect(desktopSessionApi.delete("one")).rejects.toThrow();
  vi.mocked(invoke).mockRejectedValue(new Error("offline"));
  await expect(desktopSessionApi.create("")).rejects.toThrow("offline");
});
