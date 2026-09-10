import { useEffect, useState } from "react";
import { ERROR_EVENT } from "./invoke";
import { decodeError, errorMessages, type UiError } from "./messages";

export function ErrorNotice() {
  const [error, setError] = useState<UiError>();
  useEffect(() => {
    const handler = (event: Event) => setError(decodeError((event as CustomEvent<unknown>).detail));
    window.addEventListener(ERROR_EVENT, handler);
    return () => window.removeEventListener(ERROR_EVENT, handler);
  }, []);
  if (!error) return null;
  const cancelled = error.code === "RUN_CANCELLED";
  return <section role={cancelled ? "status" : "alert"} aria-label="最近一次操作提示"
    className="fixed bottom-4 left-4 z-50 max-w-md rounded-xl border border-white/20 bg-[var(--surface-window)] p-4 text-sm shadow-xl">
    <p>{errorMessages[error.code]}</p>
    <p className="mt-1 text-xs text-white/50">{error.code}</p>
    {error.retryable && !cancelled && <p className="mt-1 text-xs">可在原操作处手动重试；不会自动调用模型。</p>}
    <button className="mt-2 underline" onClick={() => setError(undefined)}>关闭提示</button>
  </section>;
}
