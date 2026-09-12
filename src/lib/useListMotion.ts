import { useLayoutEffect, useRef, type RefObject } from "react";

/** FLIP retained rows only; no remount, focus changes, or queued animations. */
export function useListMotion(root: RefObject<HTMLElement | null>, revision: unknown) {
  const positions = useRef(new Map<string, number>());
  const animations = useRef<Animation[]>([]);
  const previousRevision = useRef(revision);
  useLayoutEffect(() => {
    const nodes = Array.from(root.current?.querySelectorAll<HTMLElement>("[data-todo-id]") ?? []);
    const changed = previousRevision.current !== revision;
    previousRevision.current = revision;
    if (changed) { animations.current.forEach(animation => animation.cancel()); animations.current = []; }
    const next = new Map<string, number>();
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    for (const node of nodes) {
      const id = node.dataset.todoId!;
      const top = node.offsetTop;
      next.set(id, top);
      const before = positions.current.get(id);
      if (changed && !reduced && before !== undefined && before !== top && node.animate) {
        animations.current.push(node.animate([
          { transform: `translateY(${before - top}px)` }, { transform: "translateY(0)" },
        ], { duration: 220, easing: "cubic-bezier(.2,.8,.2,1)" }));
      }
    }
    positions.current = next;
  });
  useLayoutEffect(() => () => animations.current.forEach(animation => animation.cancel()), []);
}
