import {
  CircleCheck,
  Ellipsis,
  Info,
  ListChecks,
  Palette,
  RefreshCw,
  Settings2,
  TriangleExclamationPoint,
} from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { call } from "../bridge";
import type { ImportGroup, Options, Status } from "../types";
import { type Anchor, Menu, Modal, Switch, anchorBelow, fmt, plural } from "./ui";

// --- header ------------------------------------------------------------------

export function Header(props: {
  options: Options | null;
  refreshing: boolean;
  onRefresh: () => void;
  onImport: () => void;
  onSettings: () => void;
  /** Shown between the title and the buttons (the pane switch). */
  children?: ReactNode;
}) {
  const btn = useRef<HTMLButtonElement>(null);
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const o = props.options;
  return (
    <header className="header">
      <div className="app-icon">
        <ListChecks size={19} strokeWidth={2.2} />
      </div>
      <div className="titles">
        <div className="title">Stepwise</div>
        <div className="subtitle">Unsuspend your deck one topic at a time, within a daily new-card limit.</div>
      </div>
      {props.children}
      <div className="header-actions">
        <button type="button" className="icon-btn" title="Recount cards" onClick={props.onRefresh}>
          <RefreshCw size={16} className={props.refreshing ? "spin" : undefined} />
        </button>
        <button
          ref={btn}
          type="button"
          className="icon-btn"
          title="Options"
          onClick={() => setAnchor(btn.current ? anchorBelow(btn.current, true) : null)}
        >
          <Ellipsis size={18} />
        </button>
      </div>
      {anchor && o && (
        <Menu
          anchor={anchor}
          minWidth={290}
          onClose={() => setAnchor(null)}
          entries={[
            { label: "Recount cards", icon: <RefreshCw size={14} />, onSelect: props.onRefresh },
            {
              label: "Import from Colorful Tags…",
              icon: <Palette size={14} />,
              onSelect: props.onImport,
              disabled: !o.colorSyncAvailable,
            },
            { separator: true },
            { label: "Settings…", icon: <Settings2 size={14} />, onSelect: props.onSettings },
          ]}
        />
      )}
    </header>
  );
}

export function Banner(props: { onImport: () => void; onDismiss: () => void }) {
  return (
    <div className="banner">
      <span className="banner-icon">
        <Palette size={17} />
      </span>
      <div className="banner-text">
        You colour tags with <b>Colorful Tags</b>. Import those colours so Stepwise knows what you've already queued
        and completed.
      </div>
      <div className="banner-actions">
        <button type="button" className="btn primary" onClick={props.onImport}>
          Import…
        </button>
        <button type="button" className="btn ghost" onClick={props.onDismiss}>
          Not now
        </button>
      </div>
    </div>
  );
}

// --- pane switch ---------------------------------------------------------------

export type Pane = "tree" | "side";

/** In a narrow window the topics and the queue take turns: this picks
 *  which one shows (hidden by the stylesheet when both fit). */
export function PaneSwitch(props: {
  pane: Pane;
  count: number;
  limit: number;
  unit: string;
  over: boolean;
  onPane: (pane: Pane) => void;
}) {
  const tab = (pane: Pane, label: ReactNode) => (
    <button
      type="button"
      role="tab"
      aria-selected={props.pane === pane}
      className={props.pane === pane ? "active" : ""}
      onClick={() => props.onPane(pane)}
    >
      {label}
    </button>
  );
  return (
    <div className="segmented pane-switch" role="tablist">
      <span className="thumb" style={{ ["--i" as string]: props.pane === "tree" ? 0 : 1 }} />
      {tab("tree", "Topics")}
      {tab(
        "side",
        <>
          Queue
          <span
            className={`count-pill${props.over ? " over" : ""}`}
            title={`${fmt(props.count)} of ${fmt(props.limit)} ${props.unit}`}
          >
            {fmt(props.count)} / {fmt(props.limit)}
          </span>
        </>,
      )}
    </div>
  );
}

// --- confirm -----------------------------------------------------------------

export interface ConfirmRequest {
  title: string;
  body: string;
  confirm: string;
  danger?: boolean;
  onConfirm: () => void;
  /** Optional second choice, e.g. "Save for later" instead of queuing. */
  alt?: { label: string; onSelect: () => void };
}

export function ConfirmDialog(props: { request: ConfirmRequest; onClose: () => void }) {
  const r = props.request;
  const ok = useRef<HTMLButtonElement>(null);
  useEffect(() => ok.current?.focus(), []);
  return (
    <Modal onClose={props.onClose} width={440}>
      <h2>{r.title}</h2>
      <p>{r.body}</p>
      <div className="modal-actions">
        <button type="button" className="btn ghost" onClick={props.onClose}>
          Cancel
        </button>
        {r.alt && (
          <button
            type="button"
            className="btn"
            onClick={() => {
              props.onClose();
              r.alt?.onSelect();
            }}
          >
            {r.alt.label}
          </button>
        )}
        <button
          ref={ok}
          type="button"
          className={`btn ${r.danger ? "danger" : "primary"}`}
          onClick={() => {
            props.onClose();
            r.onConfirm();
          }}
        >
          {r.confirm}
        </button>
      </div>
    </Modal>
  );
}

// --- import ------------------------------------------------------------------

const CHOICES: { value: Status; label: string; cls: string }[] = [
  { value: null, label: "Ignore", cls: "" },
  { value: "queued", label: "Queued", cls: "q" },
  { value: "later", label: "Later", cls: "l" },
  { value: "completed", label: "Done", cls: "d" },
];

export function ImportDialog(props: {
  onClose: () => void;
  onImport: (choices: Record<string, Status>, pins: boolean) => void;
}) {
  const [groups, setGroups] = useState<ImportGroup[] | null>(null);
  const [pins, setPins] = useState(0);
  const [choices, setChoices] = useState<Record<string, Status>>({});
  const [withPins, setWithPins] = useState(true);

  useEffect(() => {
    call<{ groups: ImportGroup[]; pins: number }>("import_info").then((r) => {
      setGroups(r.groups);
      setPins(r.pins);
      setChoices(Object.fromEntries(r.groups.map((g) => [g.color, g.suggested])));
    });
  }, []);

  return (
    <Modal onClose={props.onClose} width={560}>
      <h2>What does each colour mean?</h2>
      <p>
        Pick a status for each Colorful Tags colour you've used. Afterwards Stepwise keeps the colours in sync for
        you.
      </p>
      <div className="import-rows">
        {groups === null ? (
          <div className="skeleton" style={{ height: 120, borderRadius: 11 }} />
        ) : (
          groups.map((g) => (
            <div className="import-row" key={g.color}>
              <span className="swatch" style={{ background: g.color }} />
              <div className="import-info">
                <b>{plural(g.count, "tag")}</b>
                <div>{g.sample}</div>
              </div>
              <div className="mini-seg">
                {CHOICES.map((c) => (
                  <button
                    key={c.label}
                    type="button"
                    className={`${c.cls}${choices[g.color] === c.value ? " active" : ""}`}
                    onClick={() => setChoices({ ...choices, [g.color]: c.value })}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
      {pins > 0 && (
        <div className="check-row">
          <Switch
            checked={withPins}
            onChange={setWithPins}
            label={`Also pin the ${plural(pins, "tag")} you pinned in Colorful Tags to the top`}
          />
        </div>
      )}
      <div className="modal-actions">
        <button type="button" className="btn" onClick={props.onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={!groups}
          onClick={() => {
            props.onClose();
            props.onImport(choices, pins > 0 && withPins);
          }}
        >
          Import
        </button>
      </div>
    </Modal>
  );
}

// --- toasts ------------------------------------------------------------------

export type Tone = "ok" | "info" | "warn" | "error";
export interface Toast {
  id: number;
  message: string;
  tone: Tone;
  action?: { label: string; onClick: () => void };
}

/** A toast's first line is its headline; any further lines are details,
 *  set side by side underneath. */
function ToastText({ message }: { message: string }) {
  const [head, ...rest] = message.split("\n");
  if (!rest.length) return <span>{head}</span>;
  return (
    <span className="t-text">
      <span>{head}</span>
      <span className="t-detail">
        {rest.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </span>
    </span>
  );
}

export function Toasts({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.tone}`}>
          <span className="t-icon">
            {t.tone === "warn" || t.tone === "error" ? (
              <TriangleExclamationPoint size={15} />
            ) : t.tone === "ok" ? (
              <CircleCheck size={15} />
            ) : (
              <Info size={15} />
            )}
          </span>
          <ToastText message={t.message} />
          {t.action && (
            <button
              type="button"
              className="t-action"
              onClick={() => {
                onDismiss(t.id);
                t.action?.onClick();
              }}
            >
              {t.action.label}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
