import { invoke, isTauri } from "@tauri-apps/api/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { desktopMutations, loadDesktopTodos } from "./desktop";
import { loadPreviewTodos } from "./preview";
import { resolveTodoSource } from "./source";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(), isTauri: vi.fn() }));

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubEnv("DEV", true);
});
afterEach(() => vi.unstubAllEnvs());

describe("resolveTodoSource", () => {
  it("selects the real loader in a normal desktop window", async () => {
    vi.mocked(isTauri).mockReturnValue(true);
    expect(await resolveTodoSource("")).toEqual({ loadTodos: loadDesktopTodos, mutations: desktopMutations, preview: false });
  });

  it("leaves the normal browser disconnected instead of presenting a fake empty list", async () => {
    vi.mocked(isTauri).mockReturnValue(false);
    expect(await resolveTodoSource("")).toEqual({ loadTodos: undefined, preview: false });
    expect(invoke).not.toHaveBeenCalled();
  });

  it.each([true, false])("allows explicit development preview when desktop=%s", async (desktop) => {
    vi.mocked(isTauri).mockReturnValue(desktop);
    const source = await resolveTodoSource("?preview=todos");
    expect(source).toEqual({ loadTodos: loadPreviewTodos, preview: true });
    expect(await source.loadTodos!()).toHaveLength(24);
    expect(invoke).not.toHaveBeenCalled();
  });

  it("ignores the preview query in a production desktop build", async () => {
    vi.stubEnv("DEV", false);
    vi.mocked(isTauri).mockReturnValue(true);
    expect(await resolveTodoSource("?preview=todos")).toEqual({ loadTodos: loadDesktopTodos, mutations: desktopMutations, preview: false });
  });
});
