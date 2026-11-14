// Controls shared by AIbrahimv2's Anki add-ons, through anki-addon-kit:
// Switch, IconButton, Menu and Modal. Styled by controls.css.
// Don't edit a vendored copy (web/src/kit/ in an add-on): change it in the
// kit and run its sync.py.

import { Check } from "lucide-react";
import {
  type ReactNode,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

export function Switch(props: { checked: boolean; label: string; onChange: (v: boolean) => void }) {
  return (
    <label className="switch-row" onClick={() => props.onChange(!props.checked)}>
      <button
        type="button"
        role="switch"
        aria-checked={props.checked}
        aria-label={props.label || undefined}
        className={`switch${props.checked ? " on" : ""}`}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          props.onChange(!props.checked);
        }}
      />
      {props.label}
    </label>
  );
}

export function IconButton(props: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  size?: "sm";
  tone?: "good" | "bad";
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={["icon-btn", props.size, props.tone].filter(Boolean).join(" ")}
      title={props.label}
      aria-label={props.label}
      disabled={props.disabled}
      onClick={(e) => {
        e.stopPropagation();
        props.onClick();
      }}
    >
      {props.children}
    </button>
  );
}

// --- Escape ------------------------------------------------------------------

// Anki listens for Escape on the page's document and closes the whole window.
// So open menus and dialogs form a stack, and Escape closes the top one
// instead. The listener sits on <html>: after the page's own handlers (a
// field that takes Escape, like the shortcut recorder, stops it there) and
// before Anki's.
const layers: (() => void)[] = [];
let listening = false;

function onEscape(e: KeyboardEvent) {
  if (e.key !== "Escape" || !layers.length) return;
  e.preventDefault();
  e.stopPropagation();
  layers[layers.length - 1]();
}

/** Escape calls `close` while this is the topmost open layer. */
export function useEscape(close: () => void) {
  const latest = useRef(close);
  latest.current = close;
  useEffect(() => {
    if (!listening) {
      document.documentElement.addEventListener("keydown", onEscape);
      listening = true;
    }
    const layer = () => latest.current();
    layers.push(layer);
    return () => {
      const i = layers.lastIndexOf(layer);
      if (i >= 0) layers.splice(i, 1);
    };
  }, []);
}

// --- menus -------------------------------------------------------------------

export type MenuEntry =
  | {
      label: string;
      icon?: ReactNode;
      onSelect: () => void;
      disabled?: boolean;
      checked?: boolean;
      danger?: boolean;
      hint?: string;
      /** A small dot after the label: something new to see there. */
      dot?: boolean;
    }
  | { separator: true }
  | { section: string; tone?: number };

export interface Anchor {
  x: number;
  y: number;
  /** Align the menu's right edge to x (for buttons on the right). */
  alignRight?: boolean;
}

/** A floating menu at `anchor`, kept inside the window. Closes on outside
 *  click, Escape, blur or resize. */
export function Menu(props: {
  anchor: Anchor;
  entries: MenuEntry[];
  onClose: () => void;
  header?: ReactNode;
  minWidth?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: props.anchor.x, top: props.anchor.y });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    let left = props.anchor.alignRight ? props.anchor.x - width : props.anchor.x;
    let top = props.anchor.y;
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
    if (top + height > window.innerHeight - 8) top = Math.max(8, window.innerHeight - height - 8);
    setPos({ left, top });
  }, [props.anchor]);

  useEscape(props.onClose);
  useEffect(() => {
    const close = (e: Event) => {
      if (e.type === "mousedown" && ref.current?.contains(e.target as Node)) return;
      props.onClose();
    };
    window.addEventListener("mousedown", close, true);
    window.addEventListener("blur", close);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("mousedown", close, true);
      window.removeEventListener("blur", close);
      window.removeEventListener("resize", close);
    };
  }, [props.onClose]);

  return (
    <div
      ref={ref}
      className="menu"
      role="menu"
      style={{ left: pos.left, top: pos.top, minWidth: props.minWidth }}
      onContextMenu={(e) => e.preventDefault()}
    >
      {props.header}
      {props.entries.map((entry, i) => {
        if ("separator" in entry) return <div key={i} className="menu-sep" />;
        if ("section" in entry)
          return (
            <div
              key={i}
              className={`menu-section${entry.tone !== undefined ? ` toned step-${entry.tone % 4}` : ""}`}
            >
              {entry.section}
            </div>
          );
        return (
          <button
            key={i}
            type="button"
            role="menuitem"
            className={`menu-item${entry.danger ? " danger" : ""}`}
            disabled={entry.disabled}
            onClick={() => {
              props.onClose();
              entry.onSelect();
            }}
          >
            <span className="mi-icon">{entry.icon}</span>
            <span className="mi-label">
              {entry.label}
              {entry.dot && <span className="kit-dot" aria-label="new" />}
            </span>
            {entry.hint && <span className="mi-hint">{entry.hint}</span>}
            {entry.checked !== undefined && (
              <span className="mi-check">{entry.checked ? <Check size={14} strokeWidth={2.5} /> : null}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function anchorBelow(el: HTMLElement, alignRight = false): Anchor {
  const r = el.getBoundingClientRect();
  return { x: alignRight ? r.right : r.left, y: r.bottom + 6, alignRight };
}

// --- modal -------------------------------------------------------------------

/** A dialog over the page. Escape or a click outside closes it (and only
 *  it: see useEscape). */
export function Modal(props: { onClose: () => void; children: ReactNode; width?: number; className?: string }) {
  useEscape(props.onClose);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && props.onClose()}>
      <div
        className={props.className ? `modal ${props.className}` : "modal"}
        role="dialog"
        aria-modal="true"
        // Never wider than the window, with a margin all round.
        style={props.width ? { width: `min(${props.width}px, calc(100vw - 32px))` } : undefined}
      >
        {props.children}
      </div>
    </div>
  );
}
