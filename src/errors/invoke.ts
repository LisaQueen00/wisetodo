import { invoke as tauriInvoke } from "@tauri-apps/api/core";
import { decodeError, errorMessages } from "./messages";

export const ERROR_EVENT = "wisetodo:ui-error";
export async function invoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  try { return await (args === undefined ? tauriInvoke<T>(command) : tauriInvoke<T>(command, args)); }
  catch (failure) {
    const error = decodeError(failure);
    if (error) {
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(ERROR_EVENT, { detail: error }));
      // Keep existing local action fallbacks, including cancellation handling.
      throw errorMessages[error.code];
    }
    // Unknown transport exceptions must not become raw UI text.
    // eslint-disable-next-line preserve-caught-error -- intentionally discard potentially sensitive upstream details
    throw new Error("Desktop request failed");
  }
}
