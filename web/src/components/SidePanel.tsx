import {
  Bookmark,
  BookmarkPlus,
  Check,
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
import type { LaterPlan, Side } from "../types";
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
  onCompleteAll: () => void;
  onUnqueue: (tag: string) => void;
  onLater: (tag: string) => void;
  onUnlater: (tag: string) => void;
  onQueue: (tag: string) => void;
  onFill: () => void;
  onClear: (tag: string) => void;
  onUnsuspend: () => void;
  onBrowse: () => void;
  onReveal: (key: string) => void;
  /** The tree's selected tag, highlighted here too. */
  activeKey: string | null;
}

const TABS: Tab[] = ["queue", "later", "done"];

export function SidePanel(props: Props) {
  const { side, tab } = props;
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
          ) : side.over ? (
            <>
              <TriangleExclamationPoint size={13} />
              {fmt(-left)} over your limit · {plural(queued, "topic")}
            </>
          ) : (
            <>
              {fmt(left)} left · {plural(queued, "topic")}
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
        {tab === "queue" && (
          queued ? (
            side.queued.map((row) => (
              <div
                key={row.tag}
                className={`item${row.missing ? " missing" : ""}${props.activeKey === row.key ? " active" : ""}`}
                onClick={() => props.onReveal(row.key)}
                title={`${row.tag}\nClick to show it in the tree`}
              >
                <span className="item-bullet" />
                <ItemText title={row.title} path={row.path} step={row.step} stepIndex={row.stepIndex} />
                <RowCounts fresh={row.fresh} waiting={row.waiting} buried={row.buried} mode={side.mode} />
                <div className="item-actions">
                  <IconButton
                    size="sm"
                    tone="good"
                    label={props.unsuspendOnComplete ? "Mark completed and unsuspend its cards" : "Mark completed"}
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
              </div>
            ))
          ) : (
            <Empty icon={<Inbox size={18} />} title="Your queue is empty">
              Tick topics on the left, or search and queue every match at once.
            </Empty>
          )
        )}

        {tab === "later" && (
          side.later.length ? (
            <>
              <FillBar plan={props.laterPlan} onFill={props.onFill} />
              {side.later.map((row) => (
                <div
                  key={row.tag}
                  className={`item later-item${row.missing ? " missing" : ""}${props.activeKey === row.key ? " active" : ""}`}
                  title={`${row.tag}\nClick to show it in the tree`}
                  onClick={() => props.onReveal(row.key)}
                >
                  <span className="item-bullet" />
                  <ItemText title={row.title} path={row.path} step={row.step} stepIndex={row.stepIndex} />
                  <RowCounts fresh={row.fresh} waiting={row.waiting} buried={row.buried} mode={side.mode} />
                  <div className="item-actions">
                    <IconButton size="sm" label="Move to the queue" onClick={() => props.onQueue(row.tag)}>
                      <ListPlus size={15} />
                    </IconButton>
                    <IconButton size="sm" tone="bad" label="Remove from Later" onClick={() => props.onUnlater(row.tag)}>
                      <X size={15} />
                    </IconButton>
                  </div>
                </div>
              ))}
            </>
          ) : (
            <Empty icon={<Bookmark size={18} />} title="Nothing saved for later">
              Found a topic that won't fit this session? Hover it and click the bookmark (or press L) to park it here.
            </Empty>
          )
        )}

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
                <div className="item-meta">{row.date}</div>
                <div className="item-actions">
                  <IconButton size="sm" label="Move back to the queue" onClick={() => props.onQueue(row.tag)}>
                    <RotateCcw size={14} />
                  </IconButton>
                  <IconButton size="sm" tone="bad" label="Clear status" onClick={() => props.onClear(row.tag)}>
                    <X size={15} />
                  </IconButton>
                </div>
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
        <button type="button" className="btn primary" disabled={!queued} onClick={props.onCompleteAll}>
          <Check size={14} strokeWidth={2.6} /> Complete all
        </button>
      </div>
    </aside>
  );
}

/** "12 to unsuspend" plus, dimmed, cards already unsuspended but unstudied. */
function RowCounts(props: { fresh: number; waiting: number; buried: number; mode: Side["mode"] }) {
  const word = props.mode === "suspended" ? "to unsuspend" : props.mode === "new" ? "new" : "cards";
  const extra = props.mode === "suspended" && props.waiting > 0;
  return (
    <div
      className="item-meta"
      title={
        extra
          ? `${props.waiting} already unsuspended, not studied yet` +
            (props.buried ? ` (${props.buried} buried — back on their own)` : "")
          : undefined
      }
    >
      <b>{fmt(props.fresh)}</b>
      <div className="item-sub">{extra ? `+${fmt(props.waiting)} waiting` : word}</div>
    </div>
  );
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
      <div className="item-path">
        <StepChip step={props.step} index={props.stepIndex} />
        <span>{props.path}</span>
      </div>
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
          <b>{plural(plan.picked, "topic")}</b> fit — adds <b>+{fmt(plan.add)}</b> →{" "}
          <b>
            {fmt(plan.after)} / {fmt(plan.limit ?? 0)}
          </b>
          {plan.skipped ? ` · ${plan.skipped} too big for now` : ""}
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
