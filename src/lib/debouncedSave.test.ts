import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DebouncedSave } from "./debouncedSave";

describe("DebouncedSave", () => {
  it("coalesces a thousand edits into one latest-value write", async () => {
    const save = vi.fn(async (_value: number) => { void _value; });
    const autosave = new DebouncedSave(save);
    for (let value = 0; value < 1000; value++) {
      autosave.schedule(value);
      await vi.advanceTimersByTimeAsync(1);
    }
    expect(save).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(400);
    expect(save).toHaveBeenCalledExactlyOnceWith(999);
    await autosave.flush();
    expect(save).toHaveBeenCalledOnce();
  });

  it("keeps a burst behind a slow write serial and saves the final value", async () => {
    let release!: () => void;
    const blocked = new Promise<void>((resolve) => { release = resolve; });
    const saved: number[] = [];
    const save = vi.fn(async (value: number) => {
      if (value === -1) await blocked;
      saved.push(value);
    });
    const autosave = new DebouncedSave(save);
    autosave.schedule(-1);
    await vi.advanceTimersByTimeAsync(400);
    for (let value = 0; value < 1000; value++) autosave.schedule(value);
    await vi.advanceTimersByTimeAsync(400);
    expect(save).toHaveBeenCalledOnce();
    release();
    await autosave.flush();
    expect(saved).toEqual([-1, 999]);
    expect(save).toHaveBeenCalledTimes(2);
  });

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
