import { Check, Minus } from "lucide-react";
import type { ReactNode } from "react";
import type { Check as CheckState } from "../types";

// The shared controls come from the add-on kit (../kit/, copied from
// anki-addon-kit), so every one of the add-ons looks and behaves the same.
export { anchorBelow, IconButton, Menu, Modal, Switch, type Anchor, type MenuEntry } from "../kit/controls";

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
