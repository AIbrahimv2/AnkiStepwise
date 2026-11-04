import {
  Bookmark,
  BookmarkPlus,
  Check,
  CheckCheck,
  ChevronRight,
  CircleCheckBig,
  ExternalLink,
  Inbox,
  ListPlus,
  LockOpen,
  Minus,
  Plus,
  RotateCcw,
  TriangleExclamationPoint,
  WandSparkles,
  X,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import type { LaterPlan, QueueRow, RowGroup, Side } from "../types";
import { StepChip } from "./Tree";
import { IconButton, fmt, plural } from "./ui";

export type Tab = "queue" | "later" | "done";

interface Props {
  side: Side;
  tab: Tab;
  onTab: (tab: Tab) => void;
  laterPlan: LaterPlan | null;
  unsuspendOnComplete: boolean;
  onLimit: (value: number) => void;
  onComplete: (tags: string[]) => void;
  onFinishSession: () => void;
  onUnwatch: (tag: string) => void;
  onUnqueue: (tag: string) => void;
  onLater: (tag: string) => void;
  onUnlater: (tag: string) => void;
  onQueue: (tag: string) => void;
  onFill: () => void;
  onClear: (tag: string) => void;
  onUnsuspend: () => void;
  onBrowse: () => void;
  onReveal: (key: string) => void;
  onCompleteGroup: (tags: string[], label: string) => void;
  onLaterMany: (tags: string[]) => void;
  onQueueMany: (tags: string[]) => void;
  /** The tree's selected tag, highlighted here too. */
  activeKey: string | null;
}

const TABS: Tab[] = ["queue", "later", "done"];

export function SidePanel(props: Props) {
  const { side, tab } = props;
  const [byResource, setByResourceState] = useState(() => readPref("tq.groupBy", "resource") === "resource");
  const setByResource = (v: boolean) => {
    setByResourceState(v);
    writePref("tq.groupBy", v ? "resource" : "added");
  };
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const toggleGroup = (key: string) =>
    setCollapsed((c) => {
      const next = new Set(c);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const queued = side.queued.length;
  const pct = Math.min(100, side.limit ? (100 * side.count) / side.limit : 0);
  const left = side.limit - side.count;

  return (
    <aside className="panel">
      <section className={`meter${side.over ? " over" : ""}`}>
        <div className="meter-top">
          <div className="meter-count">{fmt(side.count)}</div>
          <div className="meter-of">/ {fmt(side.limit)} {side.unit}</div>
          <LimitStepper value={side.limit} onChange={props.onLimit} />
        </div>
        <div className="meter-bar">
          <div className="meter-fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="meter-hint">
          {!queued ? (
            "Nothing queued yet — tick topics to start a session."
          ) : (
            <>
              <span className="meter-left">
                {side.over && <TriangleExclamationPoint size={13} />}
                {side.over ? `${fmt(-left)} over your limit` : `${fmt(left)} left`}
              </span>
              <span className="meter-watched">
                {side.watched}/{queued} checked off
              </span>
            </>
          )}
        </div>
      </section>

      <div className="segmented" role="tablist" style={{ ["--tabs" as string]: 3 }}>
        <span className="thumb" style={{ ["--i" as string]: TABS.indexOf(tab) }} />
        <TabButton active={tab === "queue"} onClick={() => props.onTab("queue")} label="Queue" count={queued} />
        <TabButton active={tab === "later"} onClick={() => props.onTab("later")} label="Later" count={side.later.length} />
        <TabButton
          active={tab === "done"}
          onClick={() => props.onTab("done")}
          label="Done"
          count={side.completed.length}
        />
      </div>

      <div className="list">
        {(tab === "queue" || tab === "later") && (side.queued.length || side.later.length) ? (
          <div className="list-tools">
            <span>{tab === "later" ? "Fill takes oldest first" : ""}</span>
            <div className="mini-seg">
              <button type="button" className={byResource ? "active" : ""} onClick={() => setByResource(true)}>
                By resource
              </button>
              <button type="button" className={!byResource ? "active" : ""} onClick={() => setByResource(false)}>
                Order added
              </button>
            </div>
          </div>
        ) : null}

        {tab === "queue" &&
          (queued ? (
            <>
            <ColumnHead unit={side.unit} />
            <RowList
              rows={side.queued}
              groups={byResource ? side.queueGroups : null}
              collapsed={collapsed}
              onCollapse={toggleGroup}
              onReveal={props.onReveal}
              groupActions={(g) => (
                <>
                  <IconButton
                    size="sm"
                    tone="good"
                    label={`Check off all ${g.label} topics`}
                    onClick={() => props.onCompleteGroup(g.rows.map((r) => r.tag), g.label)}
                  >
                    <CheckCheck size={15} strokeWidth={2.4} />
                  </IconButton>
                  <IconButton size="sm" label={`Move all ${g.label} topics to Later`} onClick={() => props.onLaterMany(g.rows.map((r) => r.tag))}>
                    <BookmarkPlus size={14} />
                  </IconButton>
                </>
              )}
              renderRow={(row, path, chip) => (
                <div
                  key={row.tag}
                  className={`item${row.watched ? " watched" : ""}${row.missing ? " missing" : ""}${props.activeKey === row.key ? " active" : ""}`}
                  onClick={() => props.onReveal(row.key)}
                  title={`${row.tag}\nClick to show it in the tree`}
                >
                  {row.watched ? (
                    <span className="item-check" title="Checked off">
                      <Check size={11} strokeWidth={3} />
                    </span>
                  ) : (
                    <span className="item-bullet" />
                  )}
                  <ItemText title={row.title} path={path} step={chip ? row.step : null} stepIndex={row.stepIndex} />
                  {row.watched ? (
                    <div className="item-actions">
                      <IconButton size="sm" label="Uncheck: back to the queue" onClick={() => props.onUnwatch(row.tag)}>
                        <RotateCcw size={14} />
                      </IconButton>
                    </div>
                  ) : (
                  <div className="item-actions">
                    <IconButton
                      size="sm"
                      tone="good"
                      label={props.unsuspendOnComplete ? "Check off and unsuspend its cards" : "Check off"}
                      onClick={() => props.onComplete([row.tag])}
                    >
                      <Check size={15} strokeWidth={2.4} />
                    </IconButton>
                    <IconButton size="sm" label="Move to Later" onClick={() => props.onLater(row.tag)}>
                      <BookmarkPlus size={14} />
                    </IconButton>
                    <IconButton size="sm" tone="bad" label="Remove from queue" onClick={() => props.onUnqueue(row.tag)}>
                      <X size={15} />
                    </IconButton>
                  </div>
                  )}
                  <RowCounts row={row} mode={side.mode} />
                </div>
              )}
            />
            </>
          ) : (
            <Empty icon={<Inbox size={18} />} title="Your queue is empty">
              Tick topics on the left, or search and queue every match at once.
            </Empty>
          ))}

        {tab === "later" &&
          (side.later.length ? (
            <>
              <FillBar plan={props.laterPlan} onFill={props.onFill} />
              <ColumnHead unit={side.unit} />
              <RowList
                rows={side.later}
                groups={byResource ? side.laterGroups : null}
                collapsed={collapsed}
                onCollapse={toggleGroup}
                onReveal={props.onReveal}
                groupActions={(g) => (
                  <IconButton size="sm" label={`Move all ${g.label} topics to the queue`} onClick={() => props.onQueueMany(g.rows.map((r) => r.tag))}>
                    <ListPlus size={15} />
                  </IconButton>
                )}
                renderRow={(row, path, chip) => (
                  <div
                    key={row.tag}
                    className={`item later-item${row.missing ? " missing" : ""}${props.activeKey === row.key ? " active" : ""}`}
                    title={`${row.tag}\nClick to show it in the tree`}
                    onClick={() => props.onReveal(row.key)}
                  >
                    <span className="item-bullet" />
                    <ItemText title={row.title} path={path} step={chip ? row.step : null} stepIndex={row.stepIndex} />
                    <div className="item-actions">
                      <IconButton size="sm" label="Move to the queue" onClick={() => props.onQueue(row.tag)}>
                        <ListPlus size={15} />
                      </IconButton>
                      <IconButton size="sm" tone="bad" label="Remove from Later" onClick={() => props.onUnlater(row.tag)}>
                        <X size={15} />
                      </IconButton>
                    </div>
                    <RowCounts row={row} mode={side.mode} />
                  </div>
                )}
              />
            </>
          ) : (
            <Empty icon={<Bookmark size={18} />} title="Nothing saved for later">
              Found a topic that won't fit this session? Hover it and click the bookmark (or press L) to park it here.
            </Empty>
          ))}

        {tab === "done" && (
          side.completed.length ? (
            side.completed.map((row) => (
              <div
                key={row.tag}
                className={`item done-item${props.activeKey === row.key ? " active" : ""}`}
                title={`${row.tag}\nClick to show it in the tree`}
                onClick={() => props.onReveal(row.key)}
              >
                <span className="item-bullet" />
                <ItemText title={row.title} path={row.path} step={row.step} stepIndex={row.stepIndex} />
                <div className="item-actions">
                  <IconButton size="sm" label="Move back to the queue" onClick={() => props.onQueue(row.tag)}>
                    <RotateCcw size={14} />
                  </IconButton>
                  <IconButton size="sm" tone="bad" label="Clear status" onClick={() => props.onClear(row.tag)}>
                    <X size={15} />
                  </IconButton>
                </div>
                <div className="item-meta">{row.date}</div>
              </div>
            ))
          ) : (
            <Empty icon={<CircleCheckBig size={18} />} title="Nothing completed yet">
              Topics you finish land here with the date.
            </Empty>
          )
        )}
      </div>

      <div className="side-footer">
        <button type="button" className="btn ghost" disabled={!queued} onClick={props.onBrowse}>
          <ExternalLink size={14} /> Browse
        </button>
        <span className="spacer" />
        <button type="button" className="btn" disabled={!queued} onClick={props.onUnsuspend}>
          <LockOpen size={14} /> Unsuspend
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={!side.watched}
          onClick={props.onFinishSession}
          title="Take checked-off topics off the queue now (they stay in Done). They also leave on their own once every card is studied."
        >
          <Check size={14} strokeWidth={2.6} /> Clear checked
        </button>
      </div>
    </aside>
  );
}

/** The row's counted cards, and underneath how many still need
 *  unsuspending (or that none do). */
/** The row's counted cards. The breakdown is in the tooltip; a caption
 *  only appears when it says something the number and check don't: an
 *  unchecked topic whose cards are all unsuspended already. */
function RowCounts(props: { row: QueueRow; mode: Side["mode"] }) {
  const { row, mode } = props;
  const suspended = row.suspended ?? 0;
  const unit = mode === "suspended" ? "to unsuspend" : mode === "new" ? "new cards" : "cards";
  const tip = [
    `${fmt(row.fresh)} ${unit}`,
    mode !== "suspended" && suspended ? `${fmt(suspended)} still suspended` : null,
    row.waiting ? `${fmt(row.waiting)} unsuspended, not studied yet` : null,
    row.buried ? `${fmt(row.buried)} of those buried (back on their own)` : null,
  ]
    .filter(Boolean)
    .join("\n");
  const caption = mode === "new" && !row.watched && !suspended && row.fresh ? "unsuspended" : null;
  return (
    <div className="item-meta" title={tip}>
      <b>{fmt(row.fresh)}</b>
      {caption && <div className="item-sub">{caption}</div>}
    </div>
  );
}

/** Names the number column once, above the list, instead of labelling
 *  every row and group. Stays in view while the list scrolls. */
function ColumnHead({ unit }: { unit: string }) {
  return (
    <div className="col-head">
      <span>Topic</span>
      <span>{unit.charAt(0).toUpperCase() + unit.slice(1)}</span>
    </div>
  );
}

function readPref(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writePref(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: keep it for this session only */
  }
}

type GroupedRow<R> = R & { parent: string; sub: string };

/** Rows either flat (order added, with step chip and full path) or grouped
 *  by resource: a header per resource, and topics sharing a parent folder
 *  clustered under that folder's name. */
function RowList<R extends { tag: string; key: string; path: string }>(props: {
  rows: R[];
  groups: RowGroup<R>[] | null;
  collapsed: Set<string>;
  onCollapse: (key: string) => void;
  onReveal: (key: string) => void;
  groupActions: (group: RowGroup<R>) => ReactNode;
  renderRow: (row: R, path: string, chip: boolean) => ReactNode;
}) {
  if (!props.groups) return <>{props.rows.map((r) => props.renderRow(r, r.path, true))}</>;
  const mixedSteps = new Set(props.groups.map((g) => g.step)).size > 1;
  return (
    <>
      {props.groups.map((g) => {
        const open = !props.collapsed.has(g.key);
        return (
          <section key={g.key} className={`group step-${(g.stepIndex ?? 0) % 4}`}>
            <div className="group-head" onClick={() => props.onReveal(g.key)} title={`${g.tag}\nClick to show it in the tree`}>
              <button
                type="button"
                className={`chev${open ? " open" : ""}`}
                aria-label={open ? "Collapse" : "Expand"}
                onClick={(e) => {
                  e.stopPropagation();
                  props.onCollapse(g.key);
                }}
              >
                <ChevronRight size={14} strokeWidth={2.4} />
              </button>
              <span className="section-mark" />
              <span className="group-title">{g.label}</span>
              {mixedSteps && <StepChip step={g.step} index={g.stepIndex} />}
              <div className="item-actions">{props.groupActions(g)}</div>
              <span
                className="group-meta"
                title={g.count > 1 ? `${fmt(g.fresh)} new cards across ${g.count} topics` + (g.watched ? `, ${g.watched} checked off` : "") : undefined}
              >
                {g.count > 1 && <b>{fmt(g.fresh)}</b>}
              </span>
            </div>
            {open && <Clusters rows={g.rows} renderRow={props.renderRow} />}
          </section>
        );
      })}
    </>
  );
}

/** Consecutive rows with the same parent folder: if two or more, show the
 *  folder once as a label and the rows without a path underneath. */
function Clusters<R>(props: {
  rows: GroupedRow<R>[];
  renderRow: (row: R, path: string, chip: boolean) => ReactNode;
}) {
  const out: ReactNode[] = [];
  let i = 0;
  while (i < props.rows.length) {
    let j = i + 1;
    while (j < props.rows.length && props.rows[j].parent === props.rows[i].parent) j++;
    const run = props.rows.slice(i, j);
    if (run.length > 1 && run[0].sub) {
      out.push(
        <div key={`c:${run[0].parent}`} className="cluster">
          <div className="cluster-label">{run[0].sub}</div>
          {run.map((r) => props.renderRow(r, "", false))}
        </div>,
      );
    } else {
      for (const r of run) out.push(props.renderRow(r, r.sub, false));
    }
    i = j;
  }
  return <>{out}</>;
}

function TabButton(props: { active: boolean; label: string; count: number; onClick: () => void }) {
  return (
    <button type="button" role="tab" aria-selected={props.active} className={props.active ? "active" : ""} onClick={props.onClick}>
      {props.label} <span className="count-pill">{fmt(props.count)}</span>
    </button>
  );
}

function ItemText(props: { title: string; path: string; step: string | null; stepIndex: number | null }) {
  return (
    <div className="item-main">
      <div className="item-title">{props.title}</div>
      {(props.path || props.step) && (
        <div className="item-path">
          <StepChip step={props.step} index={props.stepIndex} />
          <span>{props.path}</span>
        </div>
      )}
    </div>
  );
}

/** "Fill your queue from Later": queues the oldest Later topics that fit. */
function FillBar({ plan, onFill }: { plan: LaterPlan | null; onFill: () => void }) {
  let text: ReactNode = "Working out what fits…";
  if (plan) {
    if (!plan.picked) text = <>Nothing here fits under your limit right now.</>;
    else
      text = (
        <>
          <span>
            <b>{plural(plan.picked, "topic")}</b> fit — adds <b>+{fmt(plan.add)}</b> →{" "}
            <b>
              {fmt(plan.after)} / {fmt(plan.limit ?? 0)}
            </b>
          </span>
          {plan.skipped ? <span className="fill-skip">{plan.skipped} too big for now</span> : null}
        </>
      );
  }
  return (
    <div className="fillbar">
      <div className="fillbar-text">{text}</div>
      <button type="button" className="btn" disabled={!plan?.picked} onClick={onFill} title="Queue the oldest Later topics that fit under your limit">
        <WandSparkles size={14} /> Fill queue
      </button>
    </div>
  );
}

function Empty(props: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="list-empty">
      <div className="empty-icon">{props.icon}</div>
      <div>{props.title}</div>
      <small>{props.children}</small>
    </div>
  );
}

function LimitStepper(props: { value: number; onChange: (v: number) => void }) {
  const [text, setText] = useState(String(props.value));
  useEffect(() => setText(String(props.value)), [props.value]);
  const commit = (v: number) => {
    const n = Math.max(1, Math.min(5000, Math.round(v)));
    setText(String(n));
    if (n !== props.value) props.onChange(n);
  };
  return (
    <div className="limit" title="Most cards you want to add in one study session">
      <span className="stepper-label">Limit</span>
      <div className="stepper">
        <button type="button" aria-label="Decrease limit" onClick={() => commit(props.value - 10)}>
          <Minus size={13} />
        </button>
        <input
          inputMode="numeric"
          value={text}
          onChange={(e) => setText(e.target.value.replace(/[^0-9]/g, ""))}
          onBlur={() => commit(Number(text) || props.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            if (e.key === "ArrowUp") commit(props.value + 10);
            if (e.key === "ArrowDown") commit(props.value - 10);
          }}
        />
        <button type="button" aria-label="Increase limit" onClick={() => commit(props.value + 10)}>
          <Plus size={13} />
        </button>
      </div>
    </div>
  );
}
