import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DebouncedSave } from "./debouncedSave";

describe("DebouncedSave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("automatically saves only the latest scheduled value", async () => {
    const save = vi.fn(async (value: string) => {
      void value;
    });
    const autosave = new DebouncedSave(save, 400);

    autosave.schedule("first");
    autosave.schedule("second");
    autosave.schedule("latest");

    await vi.advanceTimersByTimeAsync(399);
    expect(save).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(save).toHaveBeenCalledOnce();
    expect(save).toHaveBeenCalledWith("latest");
  });

  it("flushes a pending value immediately", async () => {
    const save = vi.fn(async (value: string) => {
      void value;
    });
    const autosave = new DebouncedSave(save, 400);

    autosave.schedule("save on blur");
    await autosave.flush();

    expect(save).toHaveBeenCalledOnce();
    expect(save).toHaveBeenCalledWith("save on blur");
    await vi.runAllTimersAsync();
    expect(save).toHaveBeenCalledOnce();
  });

  it("cancels an obsolete pending save", async () => {
    const save = vi.fn(async (value: string) => {
      void value;
    });
    const autosave = new DebouncedSave(save, 400);

    autosave.schedule("obsolete");
    autosave.cancel();
    await vi.runAllTimersAsync();

    expect(save).not.toHaveBeenCalled();
  });

  it("serializes saves that overlap", async () => {
    let releaseFirstSave: (() => void) | undefined;
    const firstSave = new Promise<void>((resolve) => {
      releaseFirstSave = resolve;
    });
    const events: string[] = [];
    const save = vi.fn(async (value: string) => {
      events.push(`start:${value}`);
      if (value === "first") {
        await firstSave;
      }
      events.push(`end:${value}`);
    });
    const autosave = new DebouncedSave(save, 0);

    autosave.schedule("first");
    await vi.runAllTimersAsync();
    autosave.schedule("second");
    await vi.runAllTimersAsync();

    expect(events).toEqual(["start:first"]);
    releaseFirstSave?.();
    await autosave.flush();
    expect(events).toEqual(["start:first", "end:first", "start:second", "end:second"]);
  });
});
