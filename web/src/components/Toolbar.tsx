import { ChevronsUpDown, Layers, ListPlus, Search, Star, X } from "lucide-react";
import { type ReactNode, forwardRef, useMemo, useRef, useState } from "react";
import type { ScopeOption, Summary } from "../types";
import { type Anchor, Menu, type MenuEntry, Switch, anchorBelow, fmt, plural } from "./ui";

export const SearchBox = forwardRef<
  HTMLInputElement,
  { value: string; onChange: (v: string) => void; onSubmit: () => void }
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
        title="Search topic names, e.g. brainstem or b&b cardio. Press / to focus."
        spellCheck={false}
        onChange={(e) => props.onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") props.onSubmit();
          if (e.key === "Escape" && props.value) {
            e.stopPropagation();
            props.onChange("");
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

  const entries = useMemo<MenuEntry[]>(() => {
    const f = filter.trim().toLowerCase();
    const pick = (s: ScopeOption): MenuEntry => ({
      label: s.label,
      icon: s.kind === "pinned" || s.pinned ? <Star size={13} /> : s.kind === "all" ? <Layers size={14} /> : null,
      checked: s.value === props.value,
      onSelect: () => props.onChange(s.value),
    });
    const matches = (s: ScopeOption) => !f || s.label.toLowerCase().includes(f);
    const general = props.scopes.filter((s) => (s.kind === "all" || s.kind === "pinned") && matches(s));
    const resources = props.scopes.filter((s) => s.kind === "resource" && matches(s));
    const others = props.scopes.filter((s) => s.kind === "other" && matches(s));
    const out: MenuEntry[] = general.map(pick);
    if (resources.length) out.push({ section: "Resources" }, ...resources.map(pick));
    if (others.length) out.push({ section: "Other tags" }, ...others.map(pick));
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
        {current?.kind === "pinned" ? <Star size={13} /> : <Layers size={14} />}
        <span className="picker-label">{current?.label ?? "All resources"}</span>
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

export function MatchBar(props: { summary: Summary; onQueueAll: () => void }) {
  const s = props.summary;
  const head = s.truncated ? `First ${fmt(s.count)} matches` : plural(s.count, "match", "matches");
  const bits = [s.queued ? `${fmt(s.queued)} queued` : null, s.done ? `${fmt(s.done)} done` : null].filter(Boolean);
  let tail: ReactNode = null;
  if (s.truncated) tail = <> — too many to queue at once; narrow the search or pick a resource</>;
  else if (!s.candidates) tail = <> — nothing left to queue</>;
  else
    tail = (
      <>
        {" "}— queuing the rest adds <span className="add">+{fmt(s.add)}</span> →{" "}
        <span className={s.over ? "over" : "add"}>
          {fmt(s.after)} / {fmt(s.limit)}
        </span>
      </>
    );
  return (
    <div className="matchbar">
      <div className="matchbar-text">
        <b>{head}</b>
        {bits.length ? ` · ${bits.join(" · ")}` : ""}
        {tail}
      </div>
      <button
        type="button"
        className="btn"
        disabled={s.truncated || !s.candidates}
        onClick={props.onQueueAll}
        title="Queue every match that isn't already queued or completed"
      >
        <ListPlus size={14} /> Queue {s.candidates && !s.truncated ? fmt(s.candidates) : "all"}
      </button>
    </div>
  );
}
