import {
  Check,
  CircleCheckBig,
  ExternalLink,
  Inbox,
  LockOpen,
  Minus,
  Plus,
  RotateCcw,
  TriangleExclamationPoint,
  X,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import type { Side } from "../types";
import { IconButton, fmt, plural } from "./ui";

interface Props {
  side: Side;
  unsuspendOnComplete: boolean;
  onLimit: (value: number) => void;
  onComplete: (tags: string[]) => void;
  onCompleteAll: () => void;
  onUnqueue: (tag: string) => void;
  onRequeue: (tag: string) => void;
  onClear: (tag: string) => void;
  onUnsuspend: () => void;
  onBrowse: () => void;
  onReveal: (key: string) => void;
}

export function SidePanel(props: Props) {
  const { side } = props;
  const [tab, setTab] = useState<"queue" | "done">("queue");
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

      <div className="segmented" role="tablist">
        <span className={`thumb${tab === "done" ? " right" : ""}`} />
        <button type="button" role="tab" className={tab === "queue" ? "active" : ""} onClick={() => setTab("queue")}>
          Queue <span className="count-pill">{queued}</span>
        </button>
        <button type="button" role="tab" className={tab === "done" ? "active" : ""} onClick={() => setTab("done")}>
          Completed <span className="count-pill">{side.completed.length}</span>
        </button>
      </div>

      <div className="list">
        {tab === "queue" ? (
          queued ? (
            side.queued.map((row) => (
              <div
                key={row.tag}
                className={`item${row.missing ? " missing" : ""}`}
                onDoubleClick={() => props.onReveal(row.key)}
                title={row.tag}
              >
                <span className="item-bullet" />
                <div className="item-main">
                  <div className="item-title">{row.title}</div>
                  <div className="item-path">{row.path}</div>
                </div>
                <div className="item-meta">
                  <b>{fmt(row.fresh)}</b> new
                </div>
                <div className="item-actions">
                  <IconButton
                    size="sm"
                    tone="good"
                    label={props.unsuspendOnComplete ? "Mark completed and unsuspend its cards" : "Mark completed"}
                    onClick={() => props.onComplete([row.tag])}
                  >
                    <Check size={15} strokeWidth={2.4} />
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
        ) : side.completed.length ? (
          side.completed.map((row) => (
            <div key={row.tag} className="item done-item" title={row.tag} onDoubleClick={() => props.onReveal(row.key)}>
              <span className="item-bullet" />
              <div className="item-main">
                <div className="item-title">{row.title}</div>
                <div className="item-path">{row.path}</div>
              </div>
              <div className="item-meta">{row.date}</div>
              <div className="item-actions">
                <IconButton size="sm" label="Move back to the queue" onClick={() => props.onRequeue(row.tag)}>
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
