import { useState } from "react";

const KEY = "wisetodo.panel-opacity.v1";
export const DEFAULT_OPACITY = 85;
export function validOpacity(value: number) {
  return Number.isInteger(value) && value >= 60 && value <= 100;
}
export function usePanelOpacity() {
  const [opacity, setOpacity] = useState(() => {
    try {
      const value = Number(localStorage.getItem(KEY));
      return validOpacity(value) ? value : DEFAULT_OPACITY;
    } catch { return DEFAULT_OPACITY; }
  });
  const [saveFailed, setSaveFailed] = useState(false);
  function changeOpacity(value: number) {
    if (!validOpacity(value)) return;
    setOpacity(value);
    try { localStorage.setItem(KEY, String(value)); setSaveFailed(false); }
    catch { setSaveFailed(true); }
  }
  return { opacity, changeOpacity, saveFailed };
}
