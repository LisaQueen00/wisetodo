import { Children, isValidElement, useEffect, useId, useRef, useState, type ReactNode } from "react";

/** App-owned listbox: no OS-drawn popup whose colors ignore the theme. */
export function ThemedSelect({ children, value, onChange, disabled, className, "aria-label": label }: {
  children: ReactNode; value: string | number; onChange: (event: { target: { value: string } }) => void;
  disabled?: boolean; className?: string; "aria-label": string;
}) {
  const options = Children.toArray(children).filter(isValidElement<{ value: string | number; children: ReactNode }>).map((child) => ({ value: String(child.props.value), label: child.props.children }));
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const id = useId();
  const selected = Math.max(0, options.findIndex((option) => option.value === String(value)));
  useEffect(() => { if (open) document.getElementById(`${id}-${active}`)?.scrollIntoView?.({ block: "nearest" }); }, [id, active, open]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  function choose(index: number) {
    if (disabled || !options[index]) return;
    onChange({ target: { value: options[index].value } }); setOpen(false); button.current?.focus();
  }
  return <div ref={root} className={`themed-select ${className ?? ""}`} onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }}>
    <button type="button" ref={button} role="combobox" aria-label={label} disabled={disabled}
      aria-expanded={open && !disabled} aria-controls={id} aria-haspopup="listbox"
      aria-activedescendant={open && !disabled ? `${id}-${active}` : undefined}
      onClick={() => { setActive(selected); setOpen(!open); }}
      onKeyDown={(event) => {
        if (event.nativeEvent.isComposing) return;
        if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); return; }
        if (event.key === "Tab") { setOpen(false); return; }
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault(); setOpen(true);
          setActive((old) => Math.max(0, Math.min(options.length - 1, (open ? old : selected) + (event.key === "ArrowDown" ? 1 : -1))));
        } else if (event.key === "Home" || event.key === "End") {
          event.preventDefault(); setOpen(true); setActive(event.key === "Home" ? 0 : options.length - 1);
        } else if (event.key === "Enter" || event.key === " ") {
          event.preventDefault(); if (open) choose(active); else { setActive(selected); setOpen(true); }
        } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          const index = options.findIndex((o) => String(o.label).toLocaleLowerCase().startsWith(event.key.toLocaleLowerCase()));
          if (index >= 0) { event.preventDefault(); setActive(index); setOpen(true); }
        }
      }}>{options[selected]?.label} <span aria-hidden="true">▾</span></button>
    {open && !disabled && <div id={id} role="listbox" aria-label={label}>
      {options.map((option, index) => <button type="button" role="option" key={option.value} id={`${id}-${index}`}
        tabIndex={-1} aria-selected={option.value === String(value)} data-active={active === index}
        onPointerMove={() => setActive(index)} onClick={() => choose(index)}>{option.label}</button>)}
    </div>}
  </div>;
}
