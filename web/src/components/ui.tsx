import { Check, Minus } from "lucide-react";
import {
  type ReactNode,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { Check as CheckState } from "../types";

export function Checkbox(props: {
  state: CheckState;
  locked?: boolean;
  title?: string;
  onToggle: () => void;
}) {
  const { state, locked, title, onToggle } = props;
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={state === "on" ? true : state === "partial" ? "mixed" : false}
      className={`cb ${state}${locked ? " locked" : ""}`}
      title={title}
      tabIndex={-1}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      onDoubleClick={(e) => e.stopPropagation()}
    >
      {state === "on" && <Check size={11} strokeWidth={3.2} />}
      {state === "partial" && <Minus size={11} strokeWidth={3.2} />}
    </button>
  );
}

export function Switch(props: { checked: boolean; label: string; onChange: (v: boolean) => void }) {
  return (
    <label className="switch-row" onClick={() => props.onChange(!props.checked)}>
      <button
        type="button"
        role="switch"
        aria-checked={props.checked}
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

  useEffect(() => {
    const close = (e: Event) => {
      if (e.type === "mousedown" && ref.current?.contains(e.target as Node)) return;
      props.onClose();
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && props.onClose();
    window.addEventListener("mousedown", close, true);
    window.addEventListener("blur", close);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("mousedown", close, true);
      window.removeEventListener("blur", close);
      window.removeEventListener("resize", close);
      window.removeEventListener("keydown", key);
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
            <span className="mi-label">{entry.label}</span>
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

/** Scroll a row into view where it sits in the list, not where it's stuck.
 *  A sticky header (a step, resource or folder) held at the top while you're
 *  scrolled past it already looks in view, so scrollIntoView alone barely
 *  moves: gg would land on the first row without going back up to it. */
export function scrollToRow(el: HTMLElement, block: ScrollLogicalPosition = "nearest") {
  if (getComputedStyle(el).position !== "sticky") {
    el.scrollIntoView({ block });
    return;
  }
  const was = el.style.position;
  el.style.position = "static";
  el.scrollIntoView({ block });
  el.style.position = was;
}

// --- modal -------------------------------------------------------------------

export function Modal(props: { onClose: () => void; children: ReactNode; width?: number }) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && props.onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [props.onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && props.onClose()}>
      <div
        className="modal"
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

/** Highlight each search word inside `text`. */
export function Highlight(props: { text: string; words: string[] }) {
  const { text, words } = props;
  if (!words.length) return <>{text}</>;
  const lower = text.toLowerCase();
  const marks = new Array<boolean>(text.length).fill(false);
  for (const w of words) {
    if (!w) continue;
    let i = lower.indexOf(w);
    while (i >= 0) {
      for (let j = i; j < i + w.length; j++) marks[j] = true;
      i = lower.indexOf(w, i + w.length);
    }
  }
  const parts: ReactNode[] = [];
  let start = 0;
  for (let i = 1; i <= text.length; i++) {
    if (i === text.length || marks[i] !== marks[start]) {
      const chunk = text.slice(start, i);
      parts.push(marks[start] ? <mark key={start}>{chunk}</mark> : chunk);
      start = i;
    }
  }
  return <>{parts}</>;
}

export const fmt = (n: number) => n.toLocaleString("en-US");
export const plural = (n: number, word: string, many = `${word}s`) =>
  `${fmt(n)} ${n === 1 ? word : many}`;
