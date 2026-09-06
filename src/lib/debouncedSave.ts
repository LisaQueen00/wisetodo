export const DEFAULT_SAVE_DELAY_MS = 400;

export type SaveFunction<T> = (value: T) => Promise<void>;
export type SaveErrorHandler = (error: unknown) => void;

export class DebouncedSave<T> {
  private timer: ReturnType<typeof setTimeout> | undefined;
  private pendingValue: T | undefined;
  private hasPendingValue = false;
  private saveQueue: Promise<void> = Promise.resolve();

  constructor(
    private readonly save: SaveFunction<T>,
    private readonly delayMs = DEFAULT_SAVE_DELAY_MS,
    private readonly onError: SaveErrorHandler = () => undefined,
  ) {
    if (delayMs < 0) {
      throw new RangeError("Save delay cannot be negative");
    }
  }

  schedule(value: T): void {
    this.pendingValue = value;
    this.hasPendingValue = true;
    this.clearTimer();
    this.timer = setTimeout(() => {
      void this.flush().catch(this.onError);
    }, this.delayMs);
  }

  flush(): Promise<void> {
    this.clearTimer();
    if (!this.hasPendingValue) {
      return this.saveQueue;
    }

    const value = this.pendingValue as T;
    this.pendingValue = undefined;
    this.hasPendingValue = false;

    const operation = this.saveQueue
      .catch(() => undefined)
      .then(() => this.save(value));
    this.saveQueue = operation;
    return operation;
  }

  cancel(): void {
    this.clearTimer();
    this.pendingValue = undefined;
    this.hasPendingValue = false;
  }

  private clearTimer(): void {
    if (this.timer !== undefined) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
  }
}
