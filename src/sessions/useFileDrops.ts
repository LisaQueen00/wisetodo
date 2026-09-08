import { useEffect } from "react";
import type { RefObject } from "react";
import type { SessionApi } from "./types";

export function useFileDrops(api: SessionApi, input: RefObject<HTMLTextAreaElement | null>, enabled: boolean,
  add: (paths: string[]) => void, onError: (message: string) => void) {
  useEffect(() => {
    if (!enabled || !api.listenFileDrops) return;
    let active = true;
    let unlisten: (() => void) | undefined;
    api.listenFileDrops((paths, x, y) => {
      if (!active || !input.current || input.current.disabled) return;
      const bounds = input.current.getBoundingClientRect();
      if (x < bounds.left || x >= bounds.right || y < bounds.top || y >= bounds.bottom) return;
      if (paths.some((path) => !/\.(pdf|md|markdown|txt)$/i.test(path))) {
        onError("仅支持 PDF、Markdown 和 TXT 文件；本次拖入未添加。"); return;
      }
      add(paths);
    }).then((stop) => { if (active) unlisten = stop; else stop(); }, () => {
      if (active) onError("文件拖放监听失败，请重新选择会话后重试。");
    });
    return () => { active = false; unlisten?.(); };
  }, [api, input, enabled, add, onError]);
}
