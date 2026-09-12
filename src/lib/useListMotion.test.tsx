// @vitest-environment jsdom
import { useRef } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useListMotion } from "./useListMotion";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function List({ ids }: { ids: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useListMotion(ref, ids);
  return <div ref={ref}>{ids.map(id => <div key={id} data-todo-id={id}>{id}</div>)}</div>;
}
it.each([false, true])("moves retained nodes and respects reduced motion=%s", reduced => {
  vi.stubGlobal("matchMedia", () => ({ matches: reduced }));
  vi.spyOn(HTMLElement.prototype, "offsetTop", "get").mockImplementation(function (this: HTMLElement) {
    return Array.from(this.parentElement?.children ?? []).indexOf(this) * 80;
  });
  const cancel = vi.fn();
  const animate = vi.fn(() => ({ cancel }));
  const original = HTMLElement.prototype.animate;
  HTMLElement.prototype.animate = animate as unknown as typeof original;
  try {
    const view = render(<List ids={["a", "b"]} />);
    const node = view.container.querySelector('[data-todo-id="a"]');
    view.rerender(<List ids={["b", "a"]} />);
    expect(view.container.querySelector('[data-todo-id="a"]')).toBe(node);
    expect(animate).toHaveBeenCalledTimes(reduced ? 0 : 2);
    if (!reduced) expect(animate).toHaveBeenCalledWith([
      { transform: "translateY(-80px)" }, { transform: "translateY(0)" },
    ], { duration: 220, easing: "cubic-bezier(.2,.8,.2,1)" });
    view.unmount();
    expect(cancel).toHaveBeenCalledTimes(reduced ? 0 : 2);
  } finally { HTMLElement.prototype.animate = original; }
});
