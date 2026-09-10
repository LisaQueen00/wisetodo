import { invoke } from "@tauri-apps/api/core";

export interface DesktopStatus {
  pinned: boolean; autostart: boolean | null; abnormal_exit: boolean; tray_available: boolean;
}
export interface DesktopApi {
  status: () => Promise<DesktopStatus>;
  pin: (pinned: boolean) => Promise<void>;
  autostart: (enabled: boolean) => Promise<void>;
  acknowledge: () => Promise<void>;
  restart: () => Promise<void>;
}
export const desktopApi: DesktopApi = {
  status: () => invoke("desktop_status"),
  pin: (pinned) => invoke("desktop_pin", { pinned }),
  autostart: (enabled) => invoke("desktop_autostart", { enabled }),
  acknowledge: () => invoke("desktop_acknowledge"),
  restart: () => invoke("desktop_restart"),
};
