import { ChevronRight, CornerDownLeft, Folder, SearchX, Star } from "lucide-react";
import { type KeyboardEvent, type ReactNode, memo, useEffect, useRef } from "react";
import type { AnyNode, Details, TagNode } from "../types";
import { isGroup } from "../types";
import { Checkbox, Highlight, fmt } from "./ui";

export interface FlatRow {
  key: string;
  depth: number;
  parent: string | null;
}

interface TreeProps {
  rows: FlatRow[];
  nodes: Record<string, AnyNode>;
  expanded: Set<string>;
  selected: string | null;
  words: string[];
  loading: boolean;
  emptyText: string | null;
  onSelect: (key: string) => void;
  onToggleExpand: (key: string) => void;
  onToggleQueue: (node: TagNode) => void;
  onContext: (key: string, x: number, y: number) => void;
}

export function Tree(props: TreeProps) {
  const { rows, nodes, expanded, selected } = props;
  const box = useRef<HTMLDivElement>(null);

  // Keep the selected row in view when moving with the keyboard.
  useEffect(() => {
    if (!selected || !box.current) return;
    const el = box.current.querySelector<HTMLElement>(`[data-key="${CSS.escape(selected)}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  const onKeyDown = (e: KeyboardEvent) => {
    if (!rows.length) return;
    const i = Math.max(0, rows.findIndex((r) => r.key === selected));
    const row = rows[i];
    const node = nodes[row.key];
    const move = (j: number) => props.onSelect(rows[Math.max(0, Math.min(rows.length - 1, j))].key);
    switch (e.key) {
      case "ArrowDown":
        move(selected ? i + 1 : 0);
        break;
      case "ArrowUp":
        move(i - 1);
        break;
      case "Home":
        move(0);
        break;
      case "End":
        move(rows.length - 1);
        break;
      case "ArrowRight":
        if (node?.hasKids && !expanded.has(row.key)) props.onToggleExpand(row.key);
        else if (rows[i + 1]?.parent === row.key) move(i + 1);
        break;
      case "ArrowLeft":
        if (expanded.has(row.key)) props.onToggleExpand(row.key);
        else if (row.parent) props.onSelect(row.parent);
        break;
      case " ":
        if (node && !isGroup(node)) props.onToggleQueue(node);
        break;
      case "Enter":
        if (node?.hasKids) props.onToggleExpand(row.key);
        break;
      default:
        return;
    }
    e.preventDefault();
  };

  return (
    <>
      <div className="tree-head">
        <span>Topic</span>
        <span className="r" title="Cards you haven't started yet (suspended or never studied)">New</span>
        <span className="r" title="Every card under this tag">Total</span>
        <span className="r">Status</span>
      </div>
      <div className="tree" ref={box} tabIndex={0} onKeyDown={onKeyDown} role="tree">
        {props.loading ? (
          <Skeleton />
        ) : props.emptyText ? (
          <div className="tree-empty">
            <div className="empty-icon">
              <SearchX size={18} />
            </div>
            <div>{props.emptyText}</div>
          </div>
        ) : (
          rows.map((r) => {
            const node = nodes[r.key];
            if (!node) return null;
            return (
              <TreeRow
                key={r.key}
                node={node}
                depth={r.depth}
                open={expanded.has(r.key)}
                selected={selected === r.key}
                words={props.words}
                onSelect={props.onSelect}
                onToggleExpand={props.onToggleExpand}
                onToggleQueue={props.onToggleQueue}
                onContext={props.onContext}
              />
            );
          })
        )}
      </div>
    </>
  );
}

const TreeRow = memo(function TreeRow(props: {
  node: AnyNode;
  depth: number;
  open: boolean;
  selected: boolean;
  words: string[];
  onSelect: (key: string) => void;
  onToggleExpand: (key: string) => void;
  onToggleQueue: (node: TagNode) => void;
  onContext: (key: string, x: number, y: number) => void;
}) {
  const { node, depth, open, selected } = props;
  const indent = { paddingLeft: 8 + depth * 18 };
  const chevron = node.hasKids ? (
    <button
      type="button"
      className={`chev${open ? " open" : ""}`}
      tabIndex={-1}
      aria-label={open ? "Collapse" : "Expand"}
      onClick={(e) => {
        e.stopPropagation();
        props.onToggleExpand(node.key);
      }}
    >
      <ChevronRight size={14} strokeWidth={2.4} />
    </button>
  ) : (
    <span className="chev-spacer" />
  );

  if (isGroup(node)) {
    return (
      <div
        className={`row group${selected ? " selected" : ""}`}
        data-key={node.key}
        role="treeitem"
        aria-expanded={open}
        onClick={() => props.onSelect(node.key)}
        onDoubleClick={() => props.onToggleExpand(node.key)}
      >
        <div className="cell-name" style={indent}>
          {chevron}
          <span className="group-icon">
            <Folder size={15} />
          </span>
          <span className="label">{node.label}</span>
        </div>
        <span />
        <span />
        <span className="cell-num">{fmt(node.count)} tags</span>
      </div>
    );
  }

  const [label, rootTag] = splitRootTag(node.label);
  const cls = ["row", node.top && "top", node.status === "completed" && "done", selected && "selected"]
    .filter(Boolean)
    .join(" ");
  return (
    <div
      className={cls}
      data-key={node.key}
      role="treeitem"
      aria-expanded={node.hasKids ? open : undefined}
      aria-selected={selected}
      title={node.tag}
      onClick={() => props.onSelect(node.key)}
      onDoubleClick={() => node.hasKids && props.onToggleExpand(node.key)}
      onContextMenu={(e) => {
        e.preventDefault();
        props.onSelect(node.key);
        props.onContext(node.key, e.clientX, e.clientY);
      }}
    >
      <div className="cell-name" style={indent}>
        {chevron}
        <Checkbox
          state={node.check}
          locked={node.locked}
          title={
            node.locked
              ? `Queued as part of ${node.source}`
              : node.check === "on"
                ? "Remove from queue"
                : "Add to queue"
          }
          onToggle={() => props.onToggleQueue(node)}
        />
        {node.pinned && (
          <span className="pin" title="Pinned">
            <Star size={12} fill="currentColor" />
          </span>
        )}
        <span className="label">
          <Highlight text={label} words={props.words} />
          {rootTag && <span className="root-tag">{rootTag}</span>}
        </span>
      </div>
      <span className={`cell-num${node.fresh ? " fresh" : " zero"}`}>{fmt(node.fresh)}</span>
      <span className="cell-num">{fmt(node.total)}</span>
      <span className="cell-status">
        <StatusCell node={node} />
      </span>
    </div>
  );
});

/** "B&B · Step 1" -> ["B&B", "Step 1"] so the root shows de-emphasised. */
function splitRootTag(label: string): [string, string | null] {
  const i = label.lastIndexOf(" · ");
  return i > 0 ? [label.slice(0, i), label.slice(i + 3)] : [label, null];
}

function StatusCell({ node }: { node: TagNode }) {
  if (node.status === "queued") {
    return (
      <span
        className={`badge q${node.inherited ? " inherited" : ""}`}
        title={node.inherited ? `Queued as part of ${node.source}` : "In your queue"}
      >
        <span className="dot" />
        {node.inherited ? "Included" : "Queued"}
      </span>
    );
  }
  if (node.status === "completed") {
    return (
      <span
        className={`badge d${node.inherited ? " inherited" : ""}`}
        title={`${node.doneAt === "imported" ? "Completed (imported)" : `Completed ${node.doneAt ?? ""}`}${node.inherited ? ` as part of ${node.source}` : ""}`}
      >
        Done{node.doneAt && !node.inherited && node.doneAt !== "imported" ? ` · ${node.doneAt}` : ""}
      </span>
    );
  }
  const p = node.progress;
  return (
    <>
      {node.nestedQueued > 0 && (
        <span className="nested" title={`${node.nestedQueued} topics inside are queued`}>
          <span className="dot" />
          {node.nestedQueued}
        </span>
      )}
      {p && p.done > 0 && (
        <span className="mini" title={`${p.done} of ${p.total} topics completed`}>
          <span className="mini-track">
            <span className="mini-fill" style={{ display: "block", width: `${(100 * p.done) / p.total}%` }} />
          </span>
          <span className="num">
            {p.done}/{p.total}
          </span>
        </span>
      )}
    </>
  );
}

function Skeleton() {
  const widths = [46, 38, 52, 30, 44, 36, 50, 28, 42, 34, 48, 32];
  return (
    <div aria-busy="true" aria-label="Counting cards">
      {widths.map((w, i) => (
        <div className="skeleton-row" key={i}>
          <div className="skeleton" style={{ width: 16, height: 16, borderRadius: 5 }} />
          <div className="skeleton" style={{ width: `${w}%` }} />
          <div style={{ flex: 1 }} />
          <div className="skeleton" style={{ width: 34 }} />
          <div className="skeleton" style={{ width: 40 }} />
        </div>
      ))}
    </div>
  );
}

export function DetailsBar({ details, searching }: { details: Details | null; searching: boolean }) {
  if (!details) {
    return (
      <div className="details">
        <div className="details-main">
          {searching
            ? "Tick matches to queue them, or queue them all from the bar above."
            : "Select a topic to see how many new cards it would add."}
        </div>
        <div className="hint-keys">
          <span>↑↓ move</span>
          <span>→ open</span>
          <span>space queue</span>
          <span>
            <CornerDownLeft size={11} /> expand
          </span>
        </div>
      </div>
    );
  }
  const d = details;
  let tail: ReactNode;
  if (d.status === "queued") {
    tail = d.via ? <>Queued as part of <span className="strong">{d.via}</span></> : <>In your queue</>;
  } else if (d.status === "completed") {
    tail = <>{d.date === "imported" ? "Completed (imported from Colorful Tags)" : `Completed ${d.date}`}</>;
  } else {
    tail = (
      <>
        Queuing it adds <span className="strong">+{fmt(d.add ?? 0)}</span>
        {d.overlap ? <> ({fmt(d.overlap)} already queued via other topics)</> : null}
        {" → "}
        <span className={d.over ? "over" : "strong"}>
          {fmt(d.after ?? 0)} / {fmt(d.limit)}
        </span>
      </>
    );
  }
  return (
    <div className="details">
      <div className="details-main">
        <div className="details-title">{d.title}</div>
        <div className="details-sub">
          {fmt(d.fresh)} new of {fmt(d.total)} cards · {tail}
        </div>
      </div>
    </div>
  );
}
