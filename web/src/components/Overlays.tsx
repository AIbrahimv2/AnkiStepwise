import {
  CircleCheck,
  Ellipsis,
  Info,
  Keyboard,
  Palette,
  RefreshCw,
  Settings2,
  TriangleExclamationPoint,
  X,
} from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { call } from "../bridge";
import type { ImportGroup, Options, Status } from "../types";
import { type Anchor, IconButton, Menu, Modal, Switch, anchorBelow, fmt, plural } from "./ui";

// --- header ------------------------------------------------------------------

/** Recount and the options menu (Colorful Tags import, Settings): the page's
 *  only controls that aren't about the queue itself. They sit at the end of
 *  the search toolbar, or in a narrow window's top bar. No title or logo:
 *  the window's title bar already names it. */
export function PageActions(props: {
  options: Options | null;
  refreshing: boolean;
  onRefresh: () => void;
  onImport: () => void;
  onSettings: () => void;
  onKeys: () => void;
}) {
  const btn = useRef<HTMLButtonElement>(null);
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const o = props.options;
  return (
    <div className="page-actions">
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
            { label: "Keys", icon: <Keyboard size={14} />, hint: "?", onSelect: props.onKeys },
            { label: "Settings…", icon: <Settings2 size={14} />, onSelect: props.onSettings },
          ]}
        />
      )}
    </div>
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

// --- keys ----------------------------------------------------------------------

/** Keys, what they do, and whether they're listed only with Skim
 *  installed (true) or only without it (false). */
type KeyRow = [keys: string[], does: string, skim?: boolean];

const SKIM_DOES = "Its cards in Skim, which follows as you move; p there comes back";

const KEY_SECTIONS: [string, KeyRow[]][] = [
  [
    "Topics",
    [
      [["j", "k"], "Move down / up (arrow keys too); a number first moves that many"],
      [["gg", "G"], "Top / bottom; 10G goes to row 10"],
      [["Ctrl-d", "Ctrl-u"], "Half a page down / up"],
      [["l", "h"], "Open a folder or step in / close it or go to its parent"],
      [["o", "Enter"], "Open or close a folder"],
      [["Space"], "Queue or unqueue the topic"],
      [["s"], "Save it for later, or take it off Later"],
      [["b", "p"], SKIM_DOES, true],
      [["B"], "Its cards in Anki's browser", true],
      [["b"], "Its cards in Anki's browser", false],
      [["/"], "Search topics; Enter goes to the first match"],
      [["n", "N"], "Next / previous search match"],
    ],
  ],
  [
    "Queue, Later and Done",
    [
      [["j", "k"], "Move, as in the topics (gg, G, Ctrl-d, Ctrl-u too)"],
      [["Space"], "Check the topic off, or uncheck it (Later, Done: queue it)"],
      [["s"], "Move it to Later (in Later, take it off)"],
      [["x", "dd"], "Remove it from this list"],
      [["Enter", "o"], "Show it in the topics"],
      [["b", "p"], "Its cards in Skim (on a resource, all its topics); Skim follows the cursor", true],
      [["B"], "Its cards in Anki's browser (on a resource, all its topics)", true],
      [["b"], "Its cards in Anki's browser (on a resource, all its topics)", false],
      [["gt", "gT"], "Next / previous tab"],
    ],
  ],
  [
    "Anywhere",
    [
      [["Shift-L", "Shift-H"], "To the queue / back to the topics"],
      [["u", "Cmd-Z"], "Undo"],
      [["Ctrl-r", "Cmd-Shift-Z"], "Redo"],
      [["?"], "These keys"],
    ],
  ],
];

/** Every key, by where it works; b means Skim when it's installed. */
export function KeysDialog(props: { onClose: () => void; skim: boolean }) {
  const sections = KEY_SECTIONS.map(([title, rows]) => [title, rows.filter((r) => r[2] === undefined || r[2] === props.skim)] as const);
  return (
    <Modal onClose={props.onClose} width={560}>
      <div className="dialog-head">
        <h2>Keys</h2>
        <IconButton size="sm" label="Close" onClick={props.onClose}>
          <X size={15} />
        </IconButton>
      </div>
      {sections.map(([title, rows]) => (
        <section className="keys-section" key={title}>
          <h3>{title}</h3>
          <div className="keys-table">
            {rows.map(([keys, does]) => (
              <div className="keys-row" key={keys.join(" ")}>
                <span className="keys-keys">
                  {keys.map((k) => (
                    <kbd key={k}>{k}</kbd>
                  ))}
                </span>
                <span className="keys-label">{does}</span>
              </div>
            ))}
          </div>
        </section>
      ))}
    </Modal>
  );
}
