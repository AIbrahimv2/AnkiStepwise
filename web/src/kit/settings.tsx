// Settings rows shared by AIbrahimv2's Anki add-ons, through
// anki-addon-kit: a section of rows, each with a label, a hint and a
// control, and the keyboard-shortcut recorder. Styled by controls.css.
// Don't edit a vendored copy (web/src/kit/ in an add-on): change it in the
// kit and run its sync.py.

import { X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useState } from "react";
import { IconButton } from "./controls";

export function Section(props: { title: string; children: ReactNode }) {
  return (
    <section className="set-section">
      <h3>{props.title}</h3>
      <div className="set-card">{props.children}</div>
    </section>
  );
}

/** A setting with its control on the right (or under it, when narrow). */
export function Row(props: { label: string; hint?: ReactNode; problem?: string; children: ReactNode }) {
  return (
    <div className="set-row">
      <div className="set-text">
        <div className="set-label">{props.label}</div>
        {props.hint && <div className="set-hint">{props.hint}</div>}
        {props.problem && <div className="set-problem">{props.problem}</div>}
      </div>
      <div className="set-control">{props.children}</div>
    </div>
  );
}

/** A setting whose control needs the full width, below its label. */
export function Block(props: { label: string; hint?: ReactNode; problem?: string; children: ReactNode }) {
  return (
    <div className="set-row set-block">
      <div className="set-text">
        <div className="set-label">{props.label}</div>
        {props.hint && <div className="set-hint">{props.hint}</div>}
        {props.problem && <div className="set-problem">{props.problem}</div>}
        {props.children}
      </div>
    </div>
  );
}

/** Choose one of a few values, as a small segmented control. */
export function Choice<T extends string>(props: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="mini-seg">
      {props.options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={props.value === o.value ? "active" : ""}
          onClick={() => props.onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// --- shortcut ------------------------------------------------------------------

const IS_MAC = /Mac/i.test(navigator.platform);

/** Qt's names for the modifiers, from a key event. On a Mac Qt's "Ctrl"
 *  is ⌘ and "Meta" is ⌃. */
function comboFrom(e: KeyboardEvent): string | null {
  let key: string | null = null;
  const c = e.code;
  if (/^Key[A-Z]$/.test(c)) key = c.slice(3);
  else if (/^Digit\d$/.test(c)) key = c.slice(5);
  else if (/^F\d{1,2}$/.test(c)) key = c;
  else if (c === "Space") key = "Space";
  if (!key) return null;
  const mods = [
    (IS_MAC ? e.metaKey : e.ctrlKey) && "Ctrl",
    (IS_MAC ? e.ctrlKey : e.metaKey) && "Meta",
    e.altKey && "Alt",
    e.shiftKey && "Shift",
  ].filter(Boolean);
  // Plain letters would fire while typing; F-keys may stand alone.
  if (!mods.length && !key.startsWith("F")) return null;
  return [...mods, key].join("+");
}

/** A Qt shortcut ("Ctrl+Shift+B") the way the platform writes it (⇧⌘B). */
export function displayShortcut(s: string): string {
  if (!IS_MAC) return s.replace(/\+/g, " + ");
  const sym: Record<string, string> = { Ctrl: "⌘", Meta: "⌃", Alt: "⌥", Shift: "⇧" };
  const parts = s.split("+");
  const key = parts.pop() ?? "";
  const order = ["Meta", "Alt", "Shift", "Ctrl"]; // ⌃⌥⇧⌘, the Mac order
  return order.filter((m) => parts.includes(m)).map((m) => sym[m]).join("") + key;
}

/** Click, then press the keys. Backspace clears it; Escape cancels. */
export function ShortcutField(props: { value: string; onChange: (s: string) => void }) {
  const [recording, setRecording] = useState(false);
  return (
    <div className="shortcut-field">
      <button
        type="button"
        className={`keycap-btn${recording ? " recording" : ""}`}
        onClick={() => setRecording(true)}
        onBlur={() => setRecording(false)}
        onKeyDown={(e) => {
          if (!recording) return;
          e.preventDefault();
          e.stopPropagation(); // Escape cancels recording, not the dialog
          if (e.key === "Escape") return setRecording(false);
          if (e.key === "Backspace" || e.key === "Delete") {
            props.onChange("");
            return setRecording(false);
          }
          const combo = comboFrom(e);
          if (combo) {
            props.onChange(combo);
            setRecording(false);
          }
        }}
        title="Click, then press the keys"
      >
        {recording ? "Press keys…" : props.value ? displayShortcut(props.value) : "None"}
      </button>
      {props.value && !recording && (
        <IconButton size="sm" label="No shortcut" onClick={() => props.onChange("")}>
          <X size={14} />
        </IconButton>
      )}
    </div>
  );
}
