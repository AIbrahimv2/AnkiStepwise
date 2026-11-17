// The keys you press, shown over the corner of the pane they went to (the
// tree or the queue) and faded out once you stop, so someone watching a
// screen recording can see what was pressed. Quick presses build a short
// trail (1 0 j); a key held down or pressed again shows once, with a count
// (j ×5). A number still waiting for its key stays until it's used or
// cancelled. Same as Skim's (web/src/keycast.ts there).
//
// One listener for the whole page (installKeyCast) sees every key, whoever
// handles it: the tree, the queue, or the page's own (Shift+H / Shift+L, u).

import { useEffect, useSyncExternalStore } from "react";

/** How long the keys stay after the last press. */
const FADE_AFTER_MS = 1200;
/** The fade itself (the .keycast-pill transition in styles.css). */
const FADE_MS = 300;
/** Keys in the trail at most; the oldest go first. */
const MAX_KEYS = 6;

const MODIFIERS = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock", "Fn", "OS", "Dead", "Unidentified"]);
const NAMES: Record<string, string> = {
  " ": "Space",
  ArrowDown: "↓",
  ArrowUp: "↑",
  ArrowLeft: "←",
  ArrowRight: "→",
  Escape: "Esc",
  Enter: "↵",
  Backspace: "⌫",
  Delete: "⌦",
  Tab: "⇥",
  PageDown: "PgDn",
  PageUp: "PgUp",
};
const MAC = /Mac/.test(navigator.platform);

type KeyLike = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">;

/** A key press as it should read on screen: j, ⇧G, ⌃D, Space, ↓. Null for
 *  a modifier on its own. */
export function keyLabel(e: KeyLike, mac = MAC): string | null {
  if (MODIFIERS.has(e.key)) return null;
  let key = e.key;
  // Anki's web view reports Control as ctrlKey and Cmd as metaKey, as a
  // browser does. Control+d can come as the control character "\x04",
  // which only Control makes: that alone says Control.
  const code = key.length === 1 ? key.charCodeAt(0) : -1;
  const controlChar = code >= 1 && code <= 26;
  if (controlChar) key = String.fromCharCode(code + 96);
  const control = controlChar || e.ctrlKey;
  const command = !controlChar && e.metaKey;
  const name = NAMES[key] ?? key;
  const letter = name.length === 1 && /[a-z]/i.test(name);
  // A capital is Shift and the letter: say so, the way a keyboard does, and
  // for named keys (⇧↓, ⇧Space). A shifted symbol (?) already says it.
  const shift = e.shiftKey && (letter || key.length > 1 || key === " ");
  // In the order macOS writes them: ⌃⌥⇧⌘.
  const mods = mac
    ? (control ? "⌃" : "") + (e.altKey ? "⌥" : "") + (shift ? "⇧" : "") + (command ? "⌘" : "")
    : (control ? "Ctrl+" : "") + (e.altKey ? "Alt+" : "") + (shift ? "⇧" : "") + (command ? "Win+" : "");
  return letter && mods ? mods + name.toUpperCase() : mods + name;
}

export type Pane = "tree" | "queue";
interface Pressed {
  id: number;
  label: string;
  n: number;
}
interface Cast {
  keys: Pressed[];
  pane: Pane;
  fading: boolean;
}

let cast: Cast = { keys: [], pane: "tree", fading: false };
const listeners = new Set<() => void>();
/** Panes with a number waiting for its key: the keys stay up meanwhile. */
const holds = new Set<Pane>();
let timer = 0;
let nextId = 0;

function set(next: Cast): void {
  cast = next;
  for (const fn of listeners) fn();
}

function later(): void {
  clearTimeout(timer);
  if (holds.size || !cast.keys.length) return;
  timer = window.setTimeout(() => {
    set({ ...cast, fading: true });
    timer = window.setTimeout(() => set({ ...cast, keys: [], fading: false }), FADE_MS);
  }, FADE_AFTER_MS);
}

function press(e: KeyboardEvent): void {
  const t = e.target as HTMLElement | null;
  if (t?.closest?.("input, textarea, select, [contenteditable]")) return; // typing, not keys
  if (document.querySelector(".overlay, .menu")) return; // a dialog or menu has the keys
  const label = keyLabel(e);
  if (!label) return;
  const pane: Pane = t?.closest?.('[data-keys="queue"]') ? "queue" : "tree";
  // A trail stays in one pane: keys for the other start their own.
  const keys = pane === cast.pane ? cast.keys : [];
  const last = keys[keys.length - 1];
  const next =
    last && last.label === label
      ? [...keys.slice(0, -1), { ...last, n: last.n + 1 }]
      : [...keys, { id: nextId++, label, n: 1 }].slice(-MAX_KEYS);
  clearTimeout(timer);
  set({ keys: next, pane, fading: false });
  later();
}

/** Watch the page's keys; once, at start. Ahead of every other listener, so
 *  a key a pane stops still shows. */
export function installKeyCast(): void {
  window.addEventListener("keydown", press, true);
}

/** Keep the keys up while `pane` has a number waiting for its key. */
export function useKeyCastHold(pane: Pane, on: boolean): void {
  useEffect(() => {
    if (!on) return;
    holds.add(pane);
    clearTimeout(timer);
    if (cast.fading) set({ ...cast, fading: false });
    return () => {
      holds.delete(pane);
      later();
    };
  }, [pane, on]);
}

const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

/** The keys pressed in `pane`, over its corner (inside its scroller). */
export function KeyCast(props: { pane: Pane }) {
  const c = useSyncExternalStore(subscribe, () => cast);
  if (!c.keys.length || c.pane !== props.pane) return null;
  return (
    <div className="keycast" aria-hidden="true">
      <span className={`keycast-pill${c.fading ? " fading" : ""}`}>
        {c.keys.map((k) => (
          <span key={k.id} className="kc-key" data-n={k.n > 1 ? `×${k.n}` : undefined}>
            {k.label}
          </span>
        ))}
      </span>
    </div>
  );
}
