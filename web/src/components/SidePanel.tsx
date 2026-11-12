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
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { call } from "../bridge";
import type { DoneRow, LaterPlan, QueueRow, RowGroup, Side } from "../types";
import { ctrlLetter, StepChip } from "./Tree";
import { IconButton, fmt, plural } from "./ui";

/** Done rows loaded per "Show more". */
const DONE_STEP = 200;

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
  /** b: these topics' cards (in Skim when it's installed); B: always in
   *  Anki's browser. */
  onBrowseTags: (tags: string[], title: string | undefined, anki: boolean) => void;
  /** Skim (the card browser add-on) is installed: p opens it on these
   *  topics' cards, and it follows the cursor while it shows them. */
  skim: boolean;
  onPreview: (tags: string[], title?: string) => void;
  onFollow: (tags: string[], title?: string) => void;
  /** The tree's selected tag, highlighted here too. */
  activeKey: string | null;
  /** Bumped when Shift+L (or the narrow window's switch) gives this list the
   *  keys, so the cursor shows straight away. */
  focusSignal: number;
}

const TABS: Tab[] = ["queue", "later", "done"];

/** The bits of a key event the list reads (React's and the DOM's both fit). */
type ListKey = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey" | "preventDefault" | "target">;

/** Keys that only change another key: Shift mustn't lose a typed number. */
const MODIFIER_KEYS = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock"]);

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
  // Done rows past the first page, loaded on demand (reset when Done changes).
  const [doneMore, setDoneMore] = useState<DoneRow[]>([]);
  const doneHead = side.completed[0]?.key;
  useEffect(() => setDoneMore([]), [side.doneTotal, doneHead]);
  const doneRows = doneMore.length ? [...side.completed, ...doneMore] : side.completed;
  const loadMoreDone = () =>
    call<{ rows: DoneRow[] }>("done_page", { offset: doneRows.length, limit: DONE_STEP }).then((r) =>
      setDoneMore((m) => [...m, ...r.rows]),
    );
  // --- vim keys --------------------------------------------------------------
  // Like the tree's: j/k move (with a number, 10j), gg/G top and bottom (or
  // row N), Ctrl-d/Ctrl-u half a page, h/l close a resource or go to it / open
  // it. Space does the row's main thing (check off, queue), s saves for later,
  // x or dd removes, Enter shows it in the tree, gt/gT change tab. The cursor
  // only shows while the list has the keys; Shift+H and Shift+L (in App) move
  // between the topics and this list. Rows are found in the page in display
  // order (each has data-nav), so the keys always follow what's on screen.
  const listRef = useRef<HTMLDivElement>(null);
  // The ref answers keys that come faster than a render; the state draws it.
  const [cursor, setCursorState] = useState<string | null>(null);
  const cursorRef = useRef<string | null>(null);
  const setCursor = (id: string | null) => {
    cursorRef.current = id;
    setCursorState(id);
  };
  const cursorAt = useRef(0);
  const countRef = useRef(0);
  const [count, setCountState] = useState(0);
  const setCount = (n: number) => {
    countRef.current = n;
    setCountState(n);
  };
  const lastG = useRef(0);
  const gCount = useRef(0);
  const lastD = useRef(0);
  const scrollSize = useRef(0);
  const navEls = () => [...(listRef.current?.querySelectorAll<HTMLElement>("[data-nav]") ?? [])];
  const focusedHere = () => document.activeElement === listRef.current;

  // A new tab starts at its first row.
  useEffect(() => {
    cursorAt.current = 0;
    setCursor(null);
  }, [tab]);
  // When the cursor's row goes (removed, moved to Later), take the row that
  // moved into its place.
  useLayoutEffect(() => {
    const els = navEls();
    if (!els.length) {
      if (cursor) setCursor(null);
      return;
    }
    const at = cursor ? els.findIndex((el) => el.dataset.nav === cursor) : -1;
    if (at >= 0) cursorAt.current = at;
    else if (cursor || focusedHere()) setCursor(els[Math.min(cursorAt.current, els.length - 1)].dataset.nav ?? null);
  });
  const showCursor = () => {
    const els = navEls();
    if (els.length) setCursor(els[Math.min(cursorAt.current, els.length - 1)].dataset.nav ?? null);
  };
  useEffect(() => {
    if (props.focusSignal && !cursor) showCursor();
    // Only when the list is handed the keys.
  }, [props.focusSignal]);
  useEffect(() => {
    if (!cursor || !focusedHere()) return;
    listRef.current?.querySelector(`[data-nav="${CSS.escape(cursor)}"]`)?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  const groupsHere = tab === "queue" ? side.queueGroups : tab === "later" ? side.laterGroups : [];
  const rowFor = (id: string) => {
    if (!id.startsWith("r:")) return null;
    const rows: { tag: string; key: string }[] = tab === "queue" ? side.queued : tab === "later" ? side.later : doneRows;
    return rows.find((r) => r.tag === id.slice(2)) ?? null;
  };
  const groupFor = (id: string) => (id.startsWith("g:") ? groupsHere.find((g) => g.key === id.slice(2)) ?? null : null);

  /** Space: check off or uncheck (Queue), queue (Later and Done). */
  const primary = (id: string) => {
    if (id === "more") return void loadMoreDone();
    const g = groupFor(id);
    if (g) {
      const tags = g.rows.map((r) => r.tag);
      if (tab === "queue") props.onCompleteGroup(tags, g.label);
      else if (tab === "later") props.onQueueMany(tags);
      return;
    }
    const row = rowFor(id);
    if (!row) return;
    if (tab === "queue") {
      const watched = side.queued.find((r) => r.tag === row.tag)?.watched;
      if (watched) props.onUnwatch(row.tag);
      else props.onComplete([row.tag]);
    } else props.onQueue(row.tag);
  };
  /** s: save for later (Queue), take off Later (Later). */
  const saveForLater = (id: string) => {
    const g = groupFor(id);
    if (g) {
      if (tab === "queue") props.onLaterMany(g.rows.map((r) => r.tag));
      return;
    }
    const row = rowFor(id);
    if (!row) return;
    if (tab === "queue" && !side.queued.find((r) => r.tag === row.tag)?.watched) props.onLater(row.tag);
    else if (tab === "later") props.onUnlater(row.tag);
  };
  /** The topics a row stands for: its own, or a resource's. */
  const topicsAt = (id: string): { tags: string[]; title?: string } | null => {
    const g = groupFor(id);
    if (g) return { tags: g.rows.map((r) => r.tag), title: g.label };
    const row = rowFor(id);
    return row ? { tags: [row.tag] } : null;
  };
  // Skim follows the cursor here as it does the tree's selection.
  useEffect(() => {
    if (!props.skim || !cursor || !focusedHere()) return;
    const t = topicsAt(cursor);
    if (t) props.onFollow(t.tags, t.title);
    // Only when the cursor moves.
  }, [cursor]);
  /** x or dd: take the topic off this list. Checked-off topics keep theirs
   *  until Clear checked, as their row's buttons do. */
  const removeRow = (id: string) => {
    const row = rowFor(id);
    if (!row) return;
    if (tab === "queue" && !side.queued.find((r) => r.tag === row.tag)?.watched) props.onUnqueue(row.tag);
    else if (tab === "later") props.onUnlater(row.tag);
    else if (tab === "done") props.onClear(row.tag);
  };

  const onListKey = (e: ListKey) => {
    if (MODIFIER_KEYS.has(e.key)) return;
    if (e.shiftKey && /^[hl]$/i.test(e.key)) return; // Shift+H / Shift+L switch panes (App)
    const list = listRef.current;
    const target = e.target as HTMLElement | null;
    const onControl = target !== list && !!target?.closest?.("button, input, select, textarea");
    if (onControl && (e.key === " " || e.key === "Enter")) return; // the button's own keys
    const letter = ctrlLetter(e);
    const half = letter === "d" || letter === "u";
    if ((e.ctrlKey || e.metaKey || e.altKey) && !half) return; // undo, redo, app shortcuts
    const plain = !e.ctrlKey && !e.metaKey && !e.altKey;
    // Like vim, a number can't start with 0.
    if (plain && /^[0-9]$/.test(e.key) && (e.key !== "0" || countRef.current)) {
      setCount(Math.min(countRef.current * 10 + Number(e.key), 99999));
      lastG.current = lastD.current = 0;
      e.preventDefault();
      return;
    }
    const pending = countRef.current;
    if (pending) setCount(0);
    if (e.key === "Escape") {
      if (pending) e.preventDefault();
      return;
    }
    const els = navEls(); // may be empty: gt / gT still change tab
    const handled = () => {
      e.preventDefault();
      if (!focusedHere()) list?.focus({ preventScroll: true });
    };
    const times = pending || 1;
    const now0 = cursorRef.current;
    const found = now0 ? els.findIndex((el) => el.dataset.nav === now0) : -1;
    const i = Math.max(0, found);
    const go = (j: number) => {
      if (!els.length) return;
      const k = Math.max(0, Math.min(els.length - 1, j));
      cursorAt.current = k;
      setCursor(els[k].dataset.nav ?? null);
    };
    if (half) {
      if (pending) scrollSize.current = pending;
      const n = scrollSize.current || Math.max(1, Math.floor((list?.clientHeight ?? 400) / 31 / 2));
      go(letter === "d" ? i + n : i - n);
      return handled();
    }
    let key = e.key;
    if (e.shiftKey && /^[a-z]$/.test(key)) key = key.toUpperCase(); // some keyboards
    const now = Date.now();
    // g-prefixed: gg (top, or row N), gt / gT (next / previous tab, or tab N).
    if (lastG.current && now - lastG.current < 600 && (key === "g" || key === "t" || key === "T")) {
      lastG.current = 0;
      if (key === "g") go((gCount.current || 1) - 1);
      else {
        const at = TABS.indexOf(tab);
        const next = key === "t" && gCount.current ? gCount.current - 1 : at + (key === "t" ? 1 : -(gCount.current || 1));
        props.onTab(TABS[((next % TABS.length) + TABS.length) % TABS.length]);
      }
      return handled();
    }
    if (key === "g") {
      lastG.current = now;
      gCount.current = pending;
      return handled();
    }
    lastG.current = 0;
    if (!els.length) return;
    const id = els[i].dataset.nav ?? "";
    if (key === "d") {
      if (lastD.current && now - lastD.current < 600) {
        lastD.current = 0;
        removeRow(id);
      } else lastD.current = now;
      return handled();
    }
    lastD.current = 0;
    const kind = els[i].dataset.kind;
    const group = els[i].dataset.group;
    switch (key) {
      case "j":
      case "ArrowDown":
        go(found >= 0 ? i + times : times - 1);
        break;
      case "k":
      case "ArrowUp":
        go(i - times);
        break;
      case "G":
        go(pending ? pending - 1 : els.length - 1);
        break;
      case "Home":
        go(0);
        break;
      case "End":
        go(els.length - 1);
        break;
      case "l":
      case "ArrowRight":
        if (kind === "group") {
          const g = id.slice(2);
          if (collapsed.has(g)) toggleGroup(g);
          else if (els[i + 1]?.dataset.group === g) go(i + 1);
        }
        break;
      case "h":
      case "ArrowLeft":
        if (kind === "group") {
          if (!collapsed.has(id.slice(2))) toggleGroup(id.slice(2));
        } else if (group) go(els.findIndex((el) => el.dataset.nav === `g:${group}`));
        break;
      case "Enter":
      case "o":
        if (kind === "group") toggleGroup(id.slice(2));
        else if (id === "more") loadMoreDone();
        else {
          const row = rowFor(id);
          if (row) props.onReveal(row.key);
        }
        break;
      case " ":
        primary(id);
        break;
      case "s":
        saveForLater(id);
        break;
      case "x":
        removeRow(id);
        break;
      case "b":
      case "B": {
        const t = topicsAt(id);
        if (t) props.onBrowseTags(t.tags, t.title, key === "B");
        break;
      }
      case "p": {
        const t = props.skim ? topicsAt(id) : null;
        if (!t) return;
        props.onPreview(t.tags, t.title);
        break;
      }
      default:
        return;
    }
    handled();
  };
  const cursorClass = (id: string) => (cursor === id ? " cursor" : "");

  const pct = Math.min(100, side.limit ? (100 * side.count) / side.limit : 0);
  const left = side.limit - side.count;

  return (
    <aside className="panel side-panel">
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
          count={side.doneTotal}
        />
      </div>

      <div
        className="list"
        ref={listRef}
        tabIndex={0}
        data-keys="queue"
        aria-label={`${tab === "queue" ? "Queue" : tab === "later" ? "Later" : "Done"} list`}
        onKeyDown={(e) => onListKey(e)}
        onBlur={() => countRef.current && setCount(0)}
        onFocus={(e) => e.target === e.currentTarget && !cursor && showCursor()}
      >
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
              cursor={cursor}
              renderRow={(row, path, chip, group) => (
                <div
                  key={row.tag}
                  data-nav={`r:${row.tag}`}
                  data-kind="row"
                  data-group={group}
                  className={`item${row.watched ? " watched" : ""}${row.missing ? " missing" : ""}${props.activeKey === row.key ? " active" : ""}${cursorClass(`r:${row.tag}`)}`}
                  onClick={() => {
                    setCursor(`r:${row.tag}`);
                    props.onReveal(row.key);
                  }}
                  title={`${row.tag}\nClick to show it in the tree`}
                >
                  <RowMark
                    watched={!!row.watched}
                    checkLabel={props.unsuspendOnComplete ? "Check off and unsuspend its cards" : "Check off"}
                    onCheck={() => props.onComplete([row.tag])}
                    onUncheck={() => props.onUnwatch(row.tag)}
                  />
                  <ItemText title={row.title} path={path} step={chip ? row.step : null} stepIndex={row.stepIndex} />
                  {!row.watched && (
                    <div className="item-actions">
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
                cursor={cursor}
                renderRow={(row, path, chip, group) => (
                  <div
                    key={row.tag}
                    data-nav={`r:${row.tag}`}
                    data-kind="row"
                    data-group={group}
                    className={`item later-item${row.missing ? " missing" : ""}${props.activeKey === row.key ? " active" : ""}${cursorClass(`r:${row.tag}`)}`}
                    title={`${row.tag}\nClick to show it in the tree`}
                    onClick={() => {
                      setCursor(`r:${row.tag}`);
                      props.onReveal(row.key);
                    }}
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
              Found a topic that won't fit this session? Hover it and click the bookmark (or press s) to park it here.
            </Empty>
          ))}

        {tab === "done" && (
          doneRows.length ? (
            <>
            {doneRows.map((row) => (
              <div
                key={row.tag}
                data-nav={`r:${row.tag}`}
                data-kind="row"
                className={`item done-item${props.activeKey === row.key ? " active" : ""}${cursorClass(`r:${row.tag}`)}`}
                title={`${row.tag}\nClick to show it in the tree`}
                onClick={() => {
                  setCursor(`r:${row.tag}`);
                  props.onReveal(row.key);
                }}
              >
                <span className="item-check">
                  <Check size={11} strokeWidth={3} />
                </span>
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
            ))}
            {doneRows.length < side.doneTotal && (
              <button
                type="button"
                className={`btn ghost sm show-more-done${cursorClass("more")}`}
                data-nav="more"
                data-kind="more"
                onClick={loadMoreDone}
              >
                Show {Math.min(DONE_STEP, side.doneTotal - doneRows.length).toLocaleString()} more of{" "}
                {(side.doneTotal - doneRows.length).toLocaleString()}
              </button>
            )}
            </>
          ) : (
            <Empty icon={<CircleCheckBig size={18} />} title="Nothing completed yet">
              Topics you finish land here with the date.
            </Empty>
          )
        )}
        {count > 0 && (
          <div className="count-pending" aria-live="polite">
            <span>{count}</span>
          </div>
        )}
      </div>

      <div className="side-footer">
        <button
          type="button"
          className="btn ghost browse"
          disabled={!queued}
          onClick={props.onBrowse}
          title="Show the queued topics' cards in the Browser"
        >
          <ExternalLink size={14} /> <span className="btn-label">Browse</span>
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

/** A queued row's mark is also its main action: the ring checks the topic
 *  off, and the check takes that back. */
function RowMark(props: { watched: boolean; checkLabel: string; onCheck: () => void; onUncheck: () => void }) {
  const label = props.watched ? "Uncheck: back to the queue" : props.checkLabel;
  return (
    <button
      type="button"
      className={`item-mark ${props.watched ? "item-check" : "item-bullet"}`}
      title={label}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        if (props.watched) props.onUncheck();
        else props.onCheck();
      }}
    >
      {props.watched ? (
        <>
          <Check className="mark-rest" size={11} strokeWidth={3} />
          <RotateCcw className="mark-hover" size={9} strokeWidth={3} />
        </>
      ) : (
        <Check size={10} strokeWidth={3} />
      )}
    </button>
  );
}

/** The row's counted cards, with the breakdown in the tooltip. */
function RowCounts(props: { row: QueueRow; mode: Side["mode"] }) {
  const { row, mode } = props;
  const suspended = row.suspended ?? 0;
  const unit = mode === "suspended" ? "to unsuspend" : mode === "new" ? "new cards" : "cards";
  const tip = [
    `${fmt(row.fresh)} ${unit}${row.afterToday ? " today" : ""}`,
    mode !== "suspended" && suspended ? `${fmt(suspended)} still suspended` : null,
    row.waiting ? `${fmt(row.waiting)} unsuspended, not studied yet` : null,
    row.buried ? `${fmt(row.buried)} of those buried (back on their own)` : null,
    row.afterToday
      ? `${fmt(row.afterToday)} more after today: with Bury new siblings on, Anki shows one new card per note a day`
      : null,
  ]
    .filter(Boolean)
    .join("\n");
  return (
    <div className="item-meta" title={tip}>
      <b>{fmt(row.fresh)}</b>
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
 *  by resource: a header per resource, and each topic under a heading for
 *  its folder. */
function RowList<R extends { tag: string; key: string; path: string }>(props: {
  rows: R[];
  groups: RowGroup<R>[] | null;
  collapsed: Set<string>;
  onCollapse: (key: string) => void;
  onReveal: (key: string) => void;
  groupActions: (group: RowGroup<R>) => ReactNode;
  /** The keyboard cursor's row (data-nav), to mark a resource header. */
  cursor: string | null;
  renderRow: (row: R, path: string, chip: boolean, group?: string) => ReactNode;
}) {
  if (!props.groups) return <>{props.rows.map((r) => props.renderRow(r, r.path, true))}</>;
  const mixedSteps = new Set(props.groups.map((g) => g.step)).size > 1;
  return (
    <>
      {props.groups.map((g) => {
        const open = !props.collapsed.has(g.key);
        return (
          <section key={g.key} className={`group step-${(g.stepIndex ?? 0) % 4}`}>
            <div
              className={`group-head${props.cursor === `g:${g.key}` ? " cursor" : ""}`}
              data-nav={`g:${g.key}`}
              data-kind="group"
              onClick={() => props.onReveal(g.key)}
              title={`${g.tag}\nClick to show it in the tree`}
            >
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
            {open && <Clusters rows={g.rows} renderRow={(r, path, chip) => props.renderRow(r, path, chip, g.key)} />}
          </section>
        );
      })}
    </>
  );
}

/** A resource's topics under one heading per folder, so a path always sits
 *  in the same place and each folder appears once. Topics right under the
 *  resource come first, with no heading, so none of them looks like part of
 *  the folder above it. */
function Clusters<R>(props: {
  rows: GroupedRow<R>[];
  renderRow: (row: R, path: string, chip: boolean) => ReactNode;
}) {
  const folders = new Map<string, GroupedRow<R>[]>();
  for (const row of props.rows) {
    if (!row.sub) continue;
    const rows = folders.get(row.parent);
    if (rows) rows.push(row);
    else folders.set(row.parent, [row]);
  }
  return (
    <>
      {props.rows.filter((r) => !r.sub).map((r) => props.renderRow(r, "", false))}
      {[...folders].map(([parent, rows]) => (
        <div key={`c:${parent}`} className="cluster">
          <div className="cluster-label" title={rows[0].sub}>
            {rows[0].sub}
          </div>
          {rows.map((r) => props.renderRow(r, "", false))}
        </div>
      ))}
    </>
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
