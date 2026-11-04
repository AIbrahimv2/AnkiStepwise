import { Bookmark, BookmarkMinus, BookmarkPlus, ChevronRight, CornerDownLeft, Folder, SearchX, Star } from "lucide-react";
import { type KeyboardEvent, type ReactNode, memo, useEffect, useRef } from "react";
import type { AnyNode, Details, GroupNode, TagNode } from "../types";
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
  onToggleLater: (node: TagNode) => void;
  onContext: (key: string, x: number, y: number) => void;
}

/** Small coloured "Step 1" pill; colours cycle per resource root. */
export function StepChip({ step, index }: { step: string | null; index: number | null }) {
  if (!step) return null;
  return <span className={`step-chip step-${(index ?? 0) % 4}`}>{step}</span>;
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
      case "l":
      case "L":
        if (node && !isGroup(node)) props.onToggleLater(node);
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
                onToggleLater={props.onToggleLater}
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
  onToggleLater: (node: TagNode) => void;
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

  if (isGroup(node)) return <GroupRow {...props} node={node} chevron={chevron} indent={indent} />;

  const cls = [
    "row",
    node.top && "top",
    node.status === "completed" && "done",
    node.status === "later" && "later",
    selected && "selected",
  ]
    .filter(Boolean)
    .join(" ");
  const ownLater = node.status === "later" && !node.inherited;
  const canLater = node.status !== "completed" && !(node.status && node.inherited);
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
          <Highlight text={node.label} words={props.words} />
        </span>
        {/* Under a step header the chip would just repeat it. */}
        {node.top && depth === 0 && <StepChip step={node.step} index={node.stepIndex} />}
      </div>
      <span className={`cell-num${node.fresh ? " fresh" : " zero"}`}>{fmt(node.fresh)}</span>
      <span className="cell-num">{fmt(node.total)}</span>
      <span className="cell-status">
        <StatusCell node={node} />
        {canLater && (
          <button
            type="button"
            className={`row-later${ownLater ? " on" : ""}`}
            tabIndex={-1}
            title={ownLater ? "Remove from Later (L)" : "Save for later (L)"}
            aria-label={ownLater ? "Remove from Later" : "Save for later"}
            onClick={(e) => {
              e.stopPropagation();
              props.onToggleLater(node);
            }}
          >
            {ownLater ? <BookmarkMinus size={14} /> : <BookmarkPlus size={14} />}
          </button>
        )}
      </span>
    </div>
  );
});

function GroupRow(props: {
  node: GroupNode;
  open: boolean;
  selected: boolean;
  chevron: ReactNode;
  indent: { paddingLeft: number };
  onSelect: (key: string) => void;
  onToggleExpand: (key: string) => void;
}) {
  const { node, open, selected } = props;
  const p = node.progress;
  if (node.kind === "root") {
    return (
      <div
        className={`row section step-${(node.stepIndex ?? 0) % 4}${selected ? " selected" : ""}`}
        data-key={node.key}
        role="treeitem"
        aria-expanded={open}
        title={node.sub}
        onClick={() => props.onSelect(node.key)}
        onDoubleClick={() => props.onToggleExpand(node.key)}
      >
        <div className="cell-name" style={props.indent}>
          {props.chevron}
          <span className="section-mark" />
          <span className="section-label">{node.label}</span>
          <span className="section-sub">
            {fmt(node.count)} {node.count === 1 ? "resource" : "resources"}
          </span>
        </div>
        <span className="cell-num fresh">{fmt(node.fresh ?? 0)}</span>
        <span className="cell-num">{fmt(node.total ?? 0)}</span>
        <span className="cell-status">{p && <Progress done={p.done} total={p.total} />}</span>
      </div>
    );
  }
  return (
    <div
      className={`row group${selected ? " selected" : ""}`}
      data-key={node.key}
      role="treeitem"
      aria-expanded={open}
      onClick={() => props.onSelect(node.key)}
      onDoubleClick={() => props.onToggleExpand(node.key)}
    >
      <div className="cell-name" style={props.indent}>
        {props.chevron}
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

function Progress({ done, total }: { done: number; total: number }) {
  return (
    <span className="mini" title={`${done} of ${total} topics completed`}>
      <span className="mini-track">
        <span className="mini-fill" style={{ display: "block", width: `${(100 * done) / total}%` }} />
      </span>
      <span className="num">
        {done}/{total}
      </span>
    </span>
  );
}

const sinceText = (since: string | null) => (since && since !== "imported" ? ` · ${since}` : "");

function StatusCell({ node }: { node: TagNode }) {
  const via = node.inherited ? ` as part of ${node.source}` : "";
  if (node.status === "queued") {
    return (
      <span className={`badge q${node.inherited ? " inherited" : ""}`} title={`In your queue${via}`}>
        <span className="dot" />
        {node.inherited ? "Included" : "Queued"}
      </span>
    );
  }
  if (node.status === "later") {
    return (
      <span className={`badge l${node.inherited ? " inherited" : ""}`} title={`Saved for later${via}`}>
        <Bookmark size={11} strokeWidth={2.6} />
        Later{node.inherited ? "" : sinceText(node.since)}
      </span>
    );
  }
  if (node.status === "completed") {
    return (
      <span
        className={`badge d${node.inherited ? " inherited" : ""}`}
        title={`${node.since === "imported" ? "Completed (imported)" : `Completed ${node.since ?? ""}`}${via}`}
      >
        Done{node.inherited ? "" : sinceText(node.since)}
      </span>
    );
  }
  const p = node.progress;
  return (
    <>
      {node.nestedQueued > 0 && (
        <span className="nested q" title={`${node.nestedQueued} topics inside are queued`}>
          <span className="dot" />
          {node.nestedQueued}
        </span>
      )}
      {node.nestedLater > 0 && (
        <span className="nested l" title={`${node.nestedLater} topics inside are saved for later`}>
          <Bookmark size={10} strokeWidth={2.8} />
          {node.nestedLater}
        </span>
      )}
      {p && p.done > 0 && <Progress done={p.done} total={p.total} />}
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
          <span>space queue</span>
          <span>L later</span>
          <span>
            <CornerDownLeft size={11} /> expand
          </span>
        </div>
      </div>
    );
  }
  const d = details;
  const projection = (
    <>
      Queuing it adds <span className="strong">+{fmt(d.add ?? 0)}</span>
      {d.overlap ? <> ({fmt(d.overlap)} already queued via other topics)</> : null}
      {" → "}
      <span className={d.over ? "over" : "strong"}>
        {fmt(d.after ?? 0)} / {fmt(d.limit)}
      </span>
    </>
  );
  let tail: ReactNode;
  if (d.status === "queued") {
    tail = d.via ? <>Queued as part of <span className="strong">{d.via}</span></> : <>In your queue</>;
  } else if (d.status === "completed") {
    tail = <>{d.date === "imported" ? "Completed (imported from Colorful Tags)" : `Completed ${d.date}`}</>;
  } else if (d.status === "later") {
    tail = (
      <>
        Saved for later{d.via ? <> as part of <span className="strong">{d.via}</span></> : ` ${d.date}`} ·{" "}
        {projection}
      </>
    );
  } else {
    tail = projection;
  }
  return (
    <div className="details">
      <div className="details-main">
        <div className="details-title">
          {d.title}
          <StepChip step={d.step} index={d.stepIndex} />
          {d.path && <span className="details-path">{d.path}</span>}
        </div>
        <div className="details-sub">
          {fmt(d.fresh)} new of {fmt(d.total)} cards · {tail}
        </div>
      </div>
    </div>
  );
}
