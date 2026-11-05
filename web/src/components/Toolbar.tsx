import { BookmarkPlus, ChevronsUpDown, Layers, ListPlus, Search, Star, X } from "lucide-react";
import { forwardRef, useMemo, useRef, useState } from "react";
import type { ScopeOption, Summary } from "../types";
import { type Anchor, Menu, type MenuEntry, Switch, anchorBelow, fmt, plural } from "./ui";

export const SearchBox = forwardRef<
  HTMLInputElement,
  { value: string; onChange: (v: string) => void; onSubmit: (back: boolean) => void }
>(function SearchBox(props, ref) {
  return (
    <div className="search">
      <span className="search-icon">
        <Search size={15} />
      </span>
      <input
        ref={ref}
        value={props.value}
        placeholder="Search topics…"
        title="Search topic names, e.g. brainstem or b&b cardio. / to search; Enter (Shift+Enter) goes to the first (last) match, then n / N move between matches; Esc goes back to the tree."
        spellCheck={false}
        onChange={(e) => props.onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            props.onSubmit(e.shiftKey);
          }
          // Esc leaves the box like vim's normal mode: the results stay, and
          // n / N, j / k work on them (Esc again clears the search).
          if (e.key === "Escape") {
            e.stopPropagation();
            e.currentTarget.blur();
          }
        }}
      />
      <span className="search-end">
        {props.value ? (
          <button type="button" className="icon-btn sm" aria-label="Clear search" onClick={() => props.onChange("")}>
            <X size={14} />
          </button>
        ) : (
          <span className="kbd">/</span>
        )}
      </span>
    </div>
  );
});

export function ScopePicker(props: {
  scopes: ScopeOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  const btn = useRef<HTMLButtonElement>(null);
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const [filter, setFilter] = useState("");
  const current = props.scopes.find((s) => s.value === props.value) ?? props.scopes[0];
  const manySteps = props.scopes.filter((s) => s.kind === "root").length > 1;

  // One section per step ("Step 1", "Step 2", ...), each starting with
  // "All of Step N", then "Other tags".
  const entries = useMemo<MenuEntry[]>(() => {
    const f = filter.trim().toLowerCase();
    const pick = (s: ScopeOption, inGroup: boolean): MenuEntry => ({
      label: inGroup ? (s.short ?? s.label) : s.label,
      icon:
        s.kind === "pinned" || s.pinned ? (
          <Star size={13} />
        ) : s.kind === "all" || s.kind === "root" ? (
          <Layers size={14} />
        ) : null,
      checked: s.value === props.value,
      onSelect: () => props.onChange(s.value),
    });
    const matches = (s: ScopeOption) =>
      !f || s.label.toLowerCase().includes(f) || (s.group ?? "").toLowerCase().includes(f);
    const out: MenuEntry[] = props.scopes
      .filter((s) => (s.kind === "all" || s.kind === "pinned") && matches(s))
      .map((s) => pick(s, false));
    const groups = [...new Set(props.scopes.map((s) => s.group).filter((g): g is string => !!g))];
    for (const g of groups) {
      const items = props.scopes.filter((s) => s.group === g && matches(s));
      if (!items.length) continue;
      out.push({ section: g, tone: items[0].stepIndex }, ...items.map((s) => pick(s, true)));
    }
    return out;
  }, [props.scopes, props.value, filter, props.onChange]);

  return (
    <>
      <button
        ref={btn}
        type="button"
        className="picker"
        title="Show and search only some resources"
        onClick={() => {
          setFilter("");
          setAnchor(btn.current ? anchorBelow(btn.current, true) : null);
        }}
      >
        {current?.stepIndex !== undefined ? (
          <span className={`section-mark step-${current.stepIndex % 4}`} />
        ) : current?.kind === "pinned" ? (
          <Star size={13} />
        ) : (
          <Layers size={14} />
        )}
        <span className="picker-label">{current?.label ?? "All resources"}</span>
        {current?.kind === "resource" && manySteps && <span className="picker-step">{current.group}</span>}
        <span className="muted">
          <ChevronsUpDown size={13} />
        </span>
      </button>
      {anchor && (
        <Menu
          anchor={anchor}
          entries={entries}
          minWidth={260}
          onClose={() => setAnchor(null)}
          header={
            props.scopes.length > 8 ? (
              <input
                className="menu-filter"
                autoFocus
                placeholder="Filter resources…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    const first = entries.find((x) => "onSelect" in x);
                    if (first && "onSelect" in first) {
                      setAnchor(null);
                      first.onSelect();
                    }
                  }
                }}
              />
            ) : null
          }
        />
      )}
    </>
  );
}

export function HideDoneSwitch(props: { checked: boolean; onChange: (v: boolean) => void }) {
  return <Switch checked={props.checked} label="Hide done" onChange={props.onChange} />;
}

export function MatchBar(props: { summary: Summary; at: number; onQueueAll: () => void; onLaterAll: () => void }) {
  // Just the count and the two actions. What queuing adds is in the Queue
  // button's tooltip, and going over the limit asks first anyway.
  const s = props.summary;
  const head = props.at
    ? `Match ${fmt(props.at)} of ${fmt(s.count)}`
    : s.truncated
      ? `First ${fmt(s.count)} matches`
      : plural(s.count, "match", "matches");
  const queueTitle = s.truncated
    ? "Too many matches to queue at once"
    : s.candidates
      ? `Queue the ${plural(s.candidates, "match", "matches")} not yet queued or done: adds +${fmt(s.add)} → ${fmt(s.after)} / ${fmt(s.limit)}`
      : "Every match is already queued or done";
  return (
    <div className="matchbar">
      <div className="matchbar-text">
        <b>{head}</b>
        {s.truncated && <span className="match-bit">Narrow the search or pick a resource to queue them</span>}
      </div>
      <button
        type="button"
        className="btn ghost"
        disabled={s.truncated || !s.laterCandidates}
        onClick={props.onLaterAll}
        title="Save every match that isn't queued, done or already saved for a later session"
      >
        <BookmarkPlus size={14} /> Later
      </button>
      <button type="button" className="btn" disabled={s.truncated || !s.candidates} onClick={props.onQueueAll} title={queueTitle}>
        <ListPlus size={14} /> Queue {s.candidates && !s.truncated ? fmt(s.candidates) : "all"}
      </button>
    </div>
  );
}
