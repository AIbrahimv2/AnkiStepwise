import { Bookmark, BookmarkMinus, BookmarkPlus, ChevronRight, CircleCheck, Folder, Moon, SearchX, Star } from "lucide-react";
import { type CSSProperties, type ReactNode, memo, useEffect, useRef, useState } from "react";
import type { AnyNode, Details, GroupNode, TagNode } from "../types";
import { isGroup } from "../types";
import { Checkbox, Highlight, fmt } from "./ui";

export interface FlatRow {
  key: string;
  depth: number;
  parent: string | null;
  /** For a "Show more" row: how many children are still unloaded. */
  more?: number;
}

/** Key prefix of the "Show more" row at the end of a partly loaded folder. */
export const MORE = "__more__:";

interface TreeProps {
  rows: FlatRow[];
  nodes: Record<string, AnyNode>;
  expanded: Set<string>;
  selected: string | null;
  /** Scroll to and highlight this row; `n` changes on every request. */
  flash: { key: string; n: number };
  words: string[];
  loading: boolean;
  emptyText: string | null;
  onSelect: (key: string) => void;
  onToggleExpand: (key: string) => void;
  onToggleQueue: (node: TagNode) => void;
  onToggleLater: (node: TagNode) => void;
  onLoadMore: (key: string) => void;
  onContext: (key: string, x: number, y: number) => void;
  /** n / N: jump to the next or previous search match. */
  onJumpMatch: (dir: 1 | -1) => void;
  /** Esc in the tree: clear the search, if there is one. */
  onEscape: () => void;
}

/** Small coloured "Step 1" pill; colours cycle per resource root. */
export function StepChip({ step, index }: { step: string | null; index: number | null }) {
  if (!step) return null;
  return <span className={`step-chip step-${(index ?? 0) % 4}`}>{step}</span>;
}

/** The bits of a key event the tree reads (React's and the DOM's both fit). */
type KeyLike = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "preventDefault">;

const TREE_KEYS = new Set([
  "j", "k", "h", "l", "g", "G", "o", "s", "n", "N", " ", "Enter", "Escape",
  "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End",
]);

/** Nothing on the page has focus (it's on the body). */
const pageIdle = () => !document.activeElement || document.activeElement === document.body;

export function Tree(props: TreeProps) {
  const { rows, nodes, expanded, selected } = props;
  const box = useRef<HTMLDivElement>(null);

  // Keep the selected row in view when moving with the keyboard.
  useEffect(() => {
    if (!selected || !box.current) return;
    const el = box.current.querySelector<HTMLElement>(`[data-key="${CSS.escape(selected)}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  // Revealed from the queue panel: centre it, pulse it, and take focus so
  // the arrow keys carry on from there.
  const [pulse, setPulse] = useState<string | null>(null);
  useEffect(() => {
    const { key, n } = props.flash;
    if (!n || !box.current) return;
    const el = box.current.querySelector<HTMLElement>(`[data-key="${CSS.escape(key)}"]`);
    if (!el) return;
    el.scrollIntoView({ block: "center" });
    box.current.focus({ preventScroll: true });
    setPulse(key);
    const t = setTimeout(() => setPulse(null), 1300);
    return () => clearTimeout(t);
  }, [props.flash]);

  // Vim keys: j/k move, h/l close or go up / open or go in, gg/G top and
  // bottom, Ctrl-d/Ctrl-u half a page, n/N next/previous search match.
  // Arrow keys, Home and End work too.
  const lastG = useRef(0);
  const onKeyDown = (e: KeyLike) => {
    if (e.key === "Escape") return props.onEscape(); // even when a search found nothing
    if (!rows.length) return;
    const ctrl = e.ctrlKey && !e.metaKey && !e.altKey;
    if ((e.metaKey || e.altKey || e.ctrlKey) && !ctrl) return; // leave app shortcuts alone
    const i = Math.max(0, rows.findIndex((r) => r.key === selected));
    const row = rows[i];
    const node = nodes[row.key];
    if (row.more && (e.key === "Enter" || e.key === " " || e.key === "l")) {
      e.preventDefault();
      props.onLoadMore(row.key.slice(MORE.length));
      return;
    }
    const move = (j: number) => props.onSelect(rows[Math.max(0, Math.min(rows.length - 1, j))].key);
    const halfPage = Math.max(1, Math.floor((box.current?.clientHeight ?? 600) / 30 / 2));
    let key = e.key;
    // Some keyboards report Shift+g as "g" (and so on).
    if (key === "g" && e.shiftKey) key = "G";
    if (key === "n" && e.shiftKey) key = "N";
    if (key === "n" || key === "N") {
      props.onJumpMatch(key === "n" ? 1 : -1);
      e.preventDefault();
      return;
    }

    if (ctrl) {
      if (key !== "d" && key !== "u") return;
      key = key === "d" ? "PageHalfDown" : "PageHalfUp";
    }
    if (key === "g") {
      // gg: two presses in a row
      const now = Date.now();
      const second = now - lastG.current < 600;
      lastG.current = second ? 0 : now;
      if (second) move(0);
      e.preventDefault();
      return;
    }
    lastG.current = 0;
    switch (key) {
      case "j":
      case "ArrowDown":
        move(selected ? i + 1 : 0);
        break;
      case "k":
      case "ArrowUp":
        move(i - 1);
        break;
      case "PageHalfDown":
        move(i + halfPage);
        break;
      case "PageHalfUp":
        move(i - halfPage);
        break;
      case "Home":
        move(0);
        break;
      case "G":
      case "End":
        move(rows.length - 1);
        break;
      case "l":
      case "ArrowRight":
        if (node?.hasKids && !expanded.has(row.key)) props.onToggleExpand(row.key);
        else if (rows[i + 1]?.parent === row.key) move(i + 1);
        break;
      case "h":
      case "ArrowLeft":
        if (expanded.has(row.key)) props.onToggleExpand(row.key);
        else if (row.parent) props.onSelect(row.parent);
        break;
      case " ":
        if (node && !isGroup(node)) props.onToggleQueue(node);
        break;
      case "s":
        if (node && !isGroup(node)) props.onToggleLater(node);
        break;
      case "Enter":
      case "o":
        if (node?.hasKids) props.onToggleExpand(row.key);
        break;
      default:
        return;
    }
    e.preventDefault();
  };


  // The keys work as soon as the window opens: the tree takes focus once it
  // has rows, and again whenever the window comes back, unless something
  // else (the search box, a dialog) has it.
  const hasRows = rows.length > 0;
  useEffect(() => {
    if (hasRows && pageIdle()) box.current?.focus({ preventScroll: true });
  }, [hasRows]);
  useEffect(() => {
    const onFocus = () => pageIdle() && box.current?.focus({ preventScroll: true });
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  // Tree keys pressed while focus is elsewhere on the page (after clicking a
  // queue row, say) still drive the tree; not in text fields, on buttons, or
  // with a menu or dialog open.
  const keyRef = useRef(onKeyDown);
  keyRef.current = onKeyDown;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tree = box.current;
      if (e.defaultPrevented || !tree || tree.contains(e.target as Node)) return;
      const t = e.target as HTMLElement;
      if (t.closest?.("input, textarea, select, button, [contenteditable]")) return;
      if (document.querySelector(".overlay, .menu")) return;
      const half = e.ctrlKey && !e.metaKey && !e.altKey && (e.key === "d" || e.key === "u");
      if (!half && (e.ctrlKey || e.metaKey || e.altKey || !TREE_KEYS.has(e.key))) return;
      tree.focus({ preventScroll: true });
      keyRef.current(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <>
      <div className="tree" ref={box} tabIndex={0} onKeyDown={onKeyDown} role="tree">
      {/* Inside the scroller (and sticky) so it always has the rows' width,
          whether or not a scrollbar takes room. */}
      <div className="tree-head" role="presentation">
        <span>Topic</span>
        <span className="r" title="Still suspended: the cards you add to your reviews by unsuspending them">
          Suspended
        </span>
        <span
          className="r col-wait"
          title="Already unsuspended but not studied yet: new cards waiting in Anki, plus any buried (☾) by sibling settings, which come back by themselves. Nothing to unsuspend."
        >
          Waiting
        </span>
        <span className="r col-total" title="Every card under this tag">Total</span>
        <span className="r status-head">Status</span>
      </div>
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
            if (r.more) {
              return (
                <MoreRow
                  key={r.key}
                  depth={r.depth}
                  hidden={r.more}
                  selected={selected === r.key}
                  onLoad={() => props.onLoadMore(r.key.slice(MORE.length))}
                />
              );
            }
            const node = nodes[r.key];
            if (!node) return null;
            return (
              <TreeRow
                key={r.key}
                node={node}
                depth={r.depth}
                open={expanded.has(r.key)}
                selected={selected === r.key}
                pulse={pulse === r.key}
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
  pulse: boolean;
  words: string[];
  onSelect: (key: string) => void;
  onToggleExpand: (key: string) => void;
  onToggleQueue: (node: TagNode) => void;
  onToggleLater: (node: TagNode) => void;
  onContext: (key: string, x: number, y: number) => void;
}) {
  const { node, depth, open, selected } = props;
  // How far in each level sits is up to the stylesheet (less when narrow).
  const indent = { "--depth": depth } as CSSProperties;
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
    props.pulse && "pulse",
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
      <span className={`cell-num${node.suspended ? " fresh" : " zero"}`}>{fmt(node.suspended)}</span>
      <WaitingCell waiting={node.waiting} buried={node.buried} />
      <span className="cell-num col-total">{fmt(node.total)}</span>
      <span className="cell-status">
        <StatusCell node={node} />
        {canLater ? (
          <button
            type="button"
            className={`row-later${ownLater ? " on" : ""}`}
            tabIndex={-1}
            title={ownLater ? "Remove from Later (s)" : "Save for later (s)"}
            aria-label={ownLater ? "Remove from Later" : "Save for later"}
            onClick={(e) => {
              e.stopPropagation();
              props.onToggleLater(node);
            }}
          >
            {ownLater ? <BookmarkMinus size={14} /> : <BookmarkPlus size={14} />}
          </button>
        ) : (
          // Same room as the button, so every row's status ends at one edge.
          <span className="row-later-slot" aria-hidden="true" />
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
  indent: CSSProperties;
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
        <span className="cell-num fresh">{fmt(node.suspended ?? 0)}</span>
        <WaitingCell waiting={node.waiting ?? 0} buried={node.buried ?? 0} />
        <span className="cell-num col-total">{fmt(node.total ?? 0)}</span>
        <span className="cell-status">
          {p && <Progress done={p.done} total={p.total} />}
          <span className="row-later-slot" aria-hidden="true" />
        </span>
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
      <span className="col-wait" />
      <span className="col-total" />
      <span className="cell-num">{fmt(node.count)} tags</span>
    </div>
  );
}

function MoreRow(props: { depth: number; hidden: number; selected: boolean; onLoad: () => void }) {
  return (
    <div className={`row more${props.selected ? " selected" : ""}`} role="treeitem">
      <div className="cell-name" style={{ "--depth": props.depth } as CSSProperties}>
        <button type="button" className="more-btn" onClick={props.onLoad}>
          Show {fmt(Math.min(props.hidden, 300))} more
        </button>
        <span className="more-left">{fmt(props.hidden)} not shown</span>
      </div>
    </div>
  );
}

/** Unsuspended-but-unstudied cards, dimmed: nothing to do here. A moon
 *  marks the ones buried by sibling settings (back on their own). */
function WaitingCell({ waiting, buried }: { waiting: number; buried: number }) {
  if (!waiting) return <span className="cell-num zero col-wait">–</span>;
  const tip =
    `${waiting} already unsuspended, not studied yet` +
    (buried ? ` — ${buried} buried (they come back by themselves)` : "");
  return (
    <span className="cell-num waiting col-wait" title={tip}>
      {buried > 0 && <Moon size={10} className="buried-icon" />}
      {fmt(waiting)}
    </span>
  );
}

/** Progress as a bar alone; the numbers are in its tooltip. */
function Progress({ done, total }: { done: number; total: number }) {
  const pct = Math.round((100 * done) / total);
  return (
    <span className="mini" title={`${fmt(done)} of ${fmt(total)} topics done (${pct}%)`}>
      <span className="mini-track">
        <span className="mini-fill" style={{ display: "block", width: `${(100 * done) / total}%` }} />
      </span>
    </span>
  );
}

/** When a status was set, set apart from the status word by weight and
 *  spacing rather than a separator. */
const sinceText = (since: string | null) =>
  since && since !== "imported" ? <span className="since">{since}</span> : null;

/** One thing per cell: a bookmark for Later, a check for Done (the date
 *  and why are in the tooltip), otherwise the progress bar. Queued needs no
 *  mark: the ticked box says it, and the queue panel already lists what's
 *  queued inside each resource. */
function StatusCell({ node }: { node: TagNode }) {
  const via = node.inherited ? ` as part of ${node.source}` : "";
  const when = node.since && node.since !== "imported" ? ` ${node.since}` : "";
  // Covered by a parent's status: same mark, drawn lighter.
  const weight = node.inherited ? 1.8 : 2.4;
  if (node.status === "later") {
    const title = `Saved for later${via || when}`;
    return (
      <span className="status-icon l" title={title} role="img" aria-label={title}>
        <Bookmark size={15} strokeWidth={weight} />
      </span>
    );
  }
  if (node.status === "completed") {
    const title = node.auto
      ? "Done: every card is studied"
      : node.since === "imported"
        ? `Completed (imported from Colorful Tags)${via}`
        : `Completed${via || when}`;
    return (
      <span className="status-icon d" title={title} role="img" aria-label={title}>
        <CircleCheck size={15} strokeWidth={weight} />
      </span>
    );
  }
  const p = node.progress;
  return p && p.done > 0 ? <Progress done={p.done} total={p.total} /> : null;
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
    // Nothing selected: just the keys, no instructions.
    return (
      <div className="details">
        <div className="details-main" />
        <KeyHints searching={searching} />
      </div>
    );
  }
  // The row's own columns already show its suspended, waiting and total
  // cards, so the bar sticks to what the row can't: where the topic sits,
  // what queuing it would do, and its status.
  const d = details;
  const projection =
    d.status === null || d.status === "later" ? (
      <span
        className="details-add"
        title={
          d.overlap ? `${fmt(d.overlap)} of its cards are already queued through other topics` : undefined
        }
      >
        {d.add ? (
          <>
            Adds <b>+{fmt(d.add)}</b>
            <span className={d.over ? "over" : undefined}>
              → {fmt(d.after ?? 0)} / {fmt(d.limit)}
            </span>
          </>
        ) : (
          "Adds nothing new"
        )}
      </span>
    ) : null;
  return (
    <div className="details">
      <div className="details-main">
        <div className="details-title">{d.title}</div>
        <div className="details-path">
          <StepChip step={d.step} index={d.stepIndex} />
          {d.path && <span>{d.path}</span>}
        </div>
      </div>
      <div className="details-side">
        {projection}
        <DetailsBadge d={d} />
      </div>
    </div>
  );
}

/** The topic's status, as the same badge the tree shows. */
function DetailsBadge({ d }: { d: Details }) {
  const via = d.via ? ` as part of ${d.via}` : "";
  if (d.status === "queued")
    return (
      <span className={`badge q${d.via ? " inherited" : ""}`} title={`In your queue${via}`}>
        <span className="dot" />
        {d.via ? `In ${d.via}` : "Queued"}
      </span>
    );
  if (d.status === "later")
    return (
      <span className={`badge l${d.via ? " inherited" : ""}`} title={`Saved for later${via}`}>
        <Bookmark size={11} strokeWidth={2.6} />
        {d.via ? `In ${d.via}` : "Later"}
        {!d.via && sinceText(d.date)}
      </span>
    );
  if (d.status === "completed")
    return (
      <span
        className={`badge d${d.auto ? " auto" : ""}`}
        title={d.auto ? "Done: every card is studied" : d.date === "imported" ? "Imported from Colorful Tags" : `Completed${via}`}
      >
        Done
        {!d.auto && !d.via && sinceText(d.date)}
      </span>
    );
  return null;
}

/** Vim-style keys for the tree (arrow keys work too). */
function KeyHints({ searching }: { searching: boolean }) {
  return (
    <div className="hint-keys">
      <span>
        <kbd className="kbd">j</kbd>
        <kbd className="kbd">k</kbd>move
      </span>
      <span>
        <kbd className="kbd">h</kbd>
        <kbd className="kbd">l</kbd>close/open
      </span>
      <span>
        <kbd className="kbd">space</kbd>queue
      </span>
      <span>
        <kbd className="kbd">s</kbd>later
      </span>
      <span>
        <kbd className="kbd">u</kbd>undo
      </span>
      {searching ? (
        <span>
          <kbd className="kbd">n</kbd>
          <kbd className="kbd">N</kbd>next match
        </span>
      ) : (
        <span>
          <kbd className="kbd">/</kbd>search
        </span>
      )}
    </div>
  );
}
