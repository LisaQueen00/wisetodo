// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { useFileDrops } from "./useFileDrops";
import type { SessionApi } from "./types";

it("accepts only supported files dropped within the enabled textarea and cleans up", async () => {
  let drop!: (paths: string[], x: number, y: number) => void;
  const stop = vi.fn();
  const api = { listenFileDrops: vi.fn(async (handler) => { drop = handler; return stop; }) } as unknown as SessionApi;
  const input = document.createElement("textarea");
  vi.spyOn(input, "getBoundingClientRect").mockReturnValue({ left: 100, top: 100, right: 200, bottom: 200 } as DOMRect);
  const ref = { current: input };
  const add = vi.fn(), error = vi.fn();
  const { unmount } = renderHook(() => useFileDrops(api, ref, true, add, error));
  await act(async () => {});
  drop(["D:/book.pdf"], 50, 50);
  expect(add).not.toHaveBeenCalled();
  drop(["D:/book.pdf", "D:/notes.md"], 150, 150);
  expect(add).toHaveBeenCalledExactlyOnceWith(["D:/book.pdf", "D:/notes.md"]);
  drop(["D:/book.pdf", "D:/program.exe"], 150, 150);
  expect(error).toHaveBeenCalledOnce();
  expect(add).toHaveBeenCalledTimes(1);
  input.disabled = true;
  drop(["D:/book.pdf"], 150, 150);
  expect(add).toHaveBeenCalledTimes(1);
  unmount();
  expect(stop).toHaveBeenCalledOnce();
  drop(["D:/book.pdf"], 150, 150);
  expect(add).toHaveBeenCalledTimes(1);
});

it("releases a listener that resolves after unmount", async () => {
  let resolve!: (stop: () => void) => void;
  const api = { listenFileDrops: () => new Promise<() => void>((done) => { resolve = done; }) } as unknown as SessionApi;
  const add = vi.fn(), error = vi.fn();
  const ref = { current: document.createElement("textarea") };
  const { unmount } = renderHook(() => useFileDrops(api, ref, true, add, error));
  unmount();
  const stop = vi.fn();
  await act(async () => { resolve(stop); });
  expect(stop).toHaveBeenCalledOnce();
});
