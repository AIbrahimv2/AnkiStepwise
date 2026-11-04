import {
  BookmarkMinus,
  BookmarkPlus,
  CircleCheck,
  Eraser,
  ExternalLink,
  ListMinus,
  ListPlus,
  LockOpen,
  Pin,
  PinOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { call, setReplyHandlers } from "./bridge";
import {
  Banner,
  type ConfirmRequest,
  ConfirmDialog,
  Header,
  ImportDialog,
  type Toast,
  Toasts,
  type Tone,
} from "./components/Overlays";
import { SettingsDialog } from "./components/Settings";
import { SidePanel, type Tab } from "./components/SidePanel";
import { HideDoneSwitch, MatchBar, ScopePicker, SearchBox } from "./components/Toolbar";
import { DetailsBar, type FlatRow, MORE, Tree } from "./components/Tree";
import { type Anchor, Menu, type MenuEntry, plural } from "./components/ui";
import {
  type AnyNode,
  type Boot,
  type Bundle,
  type Details,
  type LaterPlan,
  type Options,
  type PushEvent,
  type ScopeOption,
  type SearchResult,
  type SettingsSaved,
  type Side,
  type Status,
  type StatusColors,
  type Summary,
  type TagNode,
  isGroup,
} from "./types";

interface SearchState {
  query: string;
  roots: string[];
  kids: Record<string, string[]>;
  /** Child counts of folders opened from the results (for "Show more"). */
  totals: Record<string, number>;
  expanded: Set<string>;
  matches: string[];
  truncated: boolean;
}

type NodeList = { nodes: AnyNode[]; total?: number };

/** Folders load this many children at a time (some hold thousands). */
const PAGE = 300;

/** The status colours (from settings) drive the UI's queued/done/later hues. */
function applyColors(colors: StatusColors) {
  const root = document.documentElement.style;
  root.setProperty("--q-raw", colors.queued);
  root.setProperty("--d-raw", colors.completed);
  root.setProperty("--l-raw", colors.later);
}

export function App() {
  const [ready, setReady] = useState(false);
  const [side, setSide] = useState<Side | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [scopes, setScopes] = useState<ScopeOption[]>([]);
  const [scope, setScope] = useState("all");

  const [nodes, setNodes] = useState<Record<string, AnyNode>>({});
  const [kids, setKids] = useState<Record<string, string[]>>({});
  const [totals, setTotals] = useState<Record<string, number>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchState | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [details, setDetails] = useState<Details | null>(null);

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [menu, setMenu] = useState<{ anchor: Anchor; key: string } | null>(null);
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null);
  const [importing, setImporting] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<Tab>("queue");
  const [laterPlan, setLaterPlan] = useState<LaterPlan | null>(null);
  // A row to scroll to and briefly highlight (bumped on every reveal).
  const [flash, setFlash] = useState({ key: "", n: 0 });

  const searchInput = useRef<HTMLInputElement>(null);
  const searchSeq = useRef(0);
  const queryRef = useRef(query);
  queryRef.current = query;
  const expandedRef = useRef(expanded);
  expandedRef.current = expanded;
  const kidsRef = useRef(kids);
  kidsRef.current = kids;
  // Step sections start open; remember the ones you close.
  const collapsedRef = useRef(new Set<string>());

  // --- toasts --------------------------------------------------------------

  const dismissToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const toast = useCallback(
    (message: string, tone: Tone = "ok", action?: Toast["action"]) => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t.slice(-2), { id, message, tone, action }]);
      setTimeout(() => dismissToast(id), tone === "error" || action ? 6500 : 3600);
    },
    [dismissToast],
  );

  useEffect(() => {
    setReplyHandlers({
      toasts: (messages) => messages.forEach((m) => toast(m)),
      error: (message) => toast(message, "error"),
    });
  }, [toast]);

  // --- visible rows --------------------------------------------------------

  const hideDone = options?.hideCompleted ?? false;
  const rows = useMemo<FlatRow[]>(() => {
    const out: FlatRow[] = [];
    const kidMap = search ? search.kids : kids;
    const totalMap = search ? search.totals : totals;
    const open = search ? search.expanded : expanded;
    const walk = (keys: string[], depth: number, parent: string | null) => {
      for (const key of keys) {
        const n = nodes[key];
        if (!n) continue;
        if (hideDone && !isGroup(n) && n.status === "completed") continue;
        out.push({ key, depth, parent });
        if (open.has(key) && kidMap[key]) {
          walk(kidMap[key], depth + 1, key);
          const hidden = (totalMap[key] ?? 0) - kidMap[key].length;
          if (hidden > 0) out.push({ key: MORE + key, depth: depth + 1, parent: key, more: hidden });
        }
      }
    };
    walk(search ? search.roots : (kids[""] ?? []), 0, null);
    return out;
  }, [nodes, kids, totals, expanded, search, hideDone]);

  // What every mutating command needs to send back a full refresh.
  const ctx = useRef({ visible: [] as string[], matches: null as string[] | null, truncated: false, selected: null as string | null });
  ctx.current = {
    visible: rows.map((r) => r.key).filter((k) => nodes[k] && !isGroup(nodes[k])),
    matches: search ? search.matches : null,
    truncated: search?.truncated ?? false,
    selected: selected && !isGroup(nodes[selected]) ? selected : null,
  };

  // --- data plumbing -------------------------------------------------------

  /** Merge refreshed nodes, keeping display labels from the first load
   *  (status refreshes come back with plain labels). */
  const mergeNodes = useCallback((list: AnyNode[], keepLabels: boolean) => {
    setNodes((prev) => {
      const next = { ...prev };
      for (const n of list) {
        const old = prev[n.key];
        next[n.key] =
          keepLabels && old && !isGroup(old) && !isGroup(n)
            ? { ...n, label: old.label, top: old.top, pinned: old.pinned }
            : n;
      }
      return next;
    });
  }, []);

  const applyBundle = useCallback(
    (b: Bundle) => {
      setSide(b.side);
      setOptions(b.options);
      if (b.nodes) mergeNodes(b.nodes, true);
      if (b.summary !== undefined) setSummary(b.summary);
      if (b.details !== undefined) setDetails(b.details ?? null);
    },
    [mergeNodes],
  );

  const act = useCallback(
    async (cmd: string, args: Record<string, unknown> = {}) => {
      const b = await call<Bundle>(cmd, { ...ctx.current, ...args });
      applyBundle(b);
      return b;
    },
    [applyBundle],
  );

  const sync = useCallback(() => act("sync").catch(() => undefined), [act]);

  const runSearch = useCallback(
    async (q: string) => {
      const seq = ++searchSeq.current;
      const r = await call<SearchResult>("search", { query: q });
      if (seq !== searchSeq.current) return;
      mergeNodes(r.nodes, false);
      setSearch({
        query: q,
        roots: r.roots,
        kids: r.children,
        totals: {},
        expanded: new Set(Object.keys(r.children)),
        matches: r.matches,
        truncated: r.truncated,
      });
      setSummary(r.summary ?? null);
    },
    [mergeNodes],
  );

  /** (Re)load the browse tree: top level plus every expanded row. Step
   *  sections open by default (unless you closed them), and so does a lone
   *  resource. Pass `open` when the expanded set is changing in the same
   *  update. */
  const loadTree = useCallback(
    async (open?: Set<string>, minLimits: Record<string, number> = {}) => {
      const q = queryRef.current.trim();
      if (q) return runSearch(q);
      const top = await call<NodeList>("children", { key: "" });
      const want = new Set(open ?? expandedRef.current);
      for (const n of top.nodes) {
        const section = isGroup(n) && n.kind === "root";
        const lone = top.nodes.length === 1 && n.hasKids;
        if ((section || lone) && !collapsedRef.current.has(n.key)) want.add(n.key);
      }
      const keys = [...want];
      const lists = await Promise.all(
        keys.map((key) =>
          call<NodeList>("children", {
            key,
            limit: Math.max(PAGE, kidsRef.current[key]?.length ?? 0, minLimits[key] ?? 0),
          }),
        ),
      );
      mergeNodes([...top.nodes, ...lists.flatMap((l) => l.nodes)], false);
      setKids({
        "": top.nodes.map((n) => n.key),
        ...Object.fromEntries(keys.map((k, i) => [k, lists[i].nodes.map((n) => n.key)])),
      });
      setTotals(Object.fromEntries(keys.map((k, i) => [k, lists[i].total ?? lists[i].nodes.length])));
      setExpanded(want);
    },
    [mergeNodes, runSearch],
  );

  // --- boot & pushes -------------------------------------------------------

  useEffect(() => {
    call<Boot>("boot").then((b) => {
      setSide(b.side);
      setOptions(b.options);
      setScopes(b.scopes);
      setScope(b.scope);
      applyColors(b.colors);
      if (b.openSettings) setSettingsOpen(true);
      if (b.ready) {
        setReady(true);
        loadTree();
      }
    });
  }, [loadTree]);

  useEffect(() => {
    window.tagQueue = {
      push: (e: PushEvent) => {
        if (e.type === "toast") toast(e.message);
        else if (e.type === "sync") sync();
        else if (e.type === "settings") setSettingsOpen(true);
        else if (e.type === "index") {
          setReady(true);
          setRefreshing(false);
          call<{ scopes: ScopeOption[]; scope: string }>("scopes")
            .then((r) => {
              setScopes(r.scopes);
              setScope(r.scope);
            })
            .catch(() => undefined);
          loadTree().then(() => sync());
        }
      },
    };
  }, [toast, sync, loadTree]);

  // Debounced search as you type.
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      searchSeq.current++;
      setSearch(null);
      setSummary(null);
      return;
    }
    const t = setTimeout(() => ready && runSearch(q), 180);
    return () => clearTimeout(t);
  }, [query, ready, runSearch]);

  // Details for the selected row.
  useEffect(() => {
    if (!selected || isGroup(nodes[selected])) {
      setDetails(null);
      return;
    }
    let live = true;
    call<{ details: Details | null }>("details", { key: selected }).then((r) => live && setDetails(r.details));
    return () => {
      live = false;
    };
    // Re-run only when the selection changes; mutations send fresh details.
  }, [selected]);

  // "/" focuses search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === "/" && t.tagName !== "INPUT") {
        e.preventDefault();
        searchInput.current?.focus();
        searchInput.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // --- tree interactions ---------------------------------------------------

  const toggleExpand = useCallback(
    async (key: string) => {
      if (search) {
        const open = new Set(search.expanded);
        if (open.has(key)) {
          open.delete(key);
          setSearch((s) => (s ? { ...s, expanded: open } : s));
          return;
        }
        open.add(key);
        if (!search.kids[key]) {
          const r = await call<NodeList>("children", { key, limit: PAGE });
          mergeNodes(r.nodes, false);
          setSearch((s) =>
            s
              ? {
                  ...s,
                  kids: { ...s.kids, [key]: r.nodes.map((n) => n.key) },
                  totals: { ...s.totals, [key]: r.total ?? r.nodes.length },
                  expanded: open,
                }
              : s,
          );
        } else {
          setSearch((s) => (s ? { ...s, expanded: open } : s));
        }
        return;
      }
      if (expandedRef.current.has(key)) {
        collapsedRef.current.add(key);
        setExpanded((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
        return;
      }
      collapsedRef.current.delete(key);
      const r = await call<NodeList>("children", { key, limit: PAGE });
      mergeNodes(r.nodes, false);
      setKids((k) => ({ ...k, [key]: r.nodes.map((n) => n.key) }));
      setTotals((t) => ({ ...t, [key]: r.total ?? r.nodes.length }));
      setExpanded((prev) => new Set(prev).add(key));
    },
    [search, mergeNodes],
  );

  /** Next page of a big folder. */
  const loadMore = useCallback(
    async (key: string) => {
      const have = (search ? search.kids[key] : kidsRef.current[key]) ?? [];
      const r = await call<NodeList>("children", { key, offset: have.length, limit: PAGE });
      mergeNodes(r.nodes, false);
      const keys = [...have, ...r.nodes.map((n) => n.key)];
      const total = r.total ?? keys.length;
      if (search) {
        setSearch((s) =>
          s ? { ...s, kids: { ...s.kids, [key]: keys }, totals: { ...s.totals, [key]: total } } : s,
        );
      } else {
        setKids((k) => ({ ...k, [key]: keys }));
        setTotals((t) => ({ ...t, [key]: total }));
      }
    },
    [search, mergeNodes],
  );

  /** After queuing: if that went over the limit, offer to park those
   *  topics in Later instead. */
  const warnIfOver = useCallback(
    (b: Bundle, tags: string[]) => {
      if (!b.side.over) return;
      toast(`${(b.side.count - b.side.limit).toLocaleString()} over your ${b.side.limit}-card limit`, "warn", {
        label: "Move to Later",
        onClick: () => {
          call<Bundle>("later", { ...ctx.current, tags }).then(applyBundle);
        },
      });
    },
    [toast, applyBundle],
  );

  const toggleQueue = useCallback(
    async (n: TagNode) => {
      if (n.locked) {
        toast(`Already queued as part of ${n.source}`, "info");
        return;
      }
      if (n.check === "on") {
        await act("unqueue", { tags: [n.tag] });
      } else {
        warnIfOver(await act("queue", { tags: [n.tag] }), [n.tag]);
      }
    },
    [act, toast, warnIfOver],
  );

  const toggleLater = useCallback(
    (n: TagNode) => {
      if (n.status === "completed" || (n.status && n.inherited)) return;
      if (n.status === "later") act("unlater", { tags: [n.tag] });
      else act("later", { tags: [n.tag] });
    },
    [act],
  );

  const complete = useCallback((tags: string[]) => act("complete", { tags }), [act]);

  const finishSession = () => {
    if (!side?.watched) return;
    const left = side.toWatch;
    setConfirm({
      title: `Clear ${plural(side.watched, "checked-off topic")}?`,
      body:
        "They leave the queue now and stay in Done, so their unstudied new cards stop counting toward your daily limit. " +
        "(Checked-off topics leave on their own once every card is studied.)" +
        (left ? ` ${plural(left, "unchecked topic")} stay queued.` : ""),
      confirm: "Clear checked",
      onConfirm: () => act("finish_session"),
    });
  };

  const queueMatches = () => {
    if (!summary) return;
    const go = () => act("queue_matches");
    if (summary.over) {
      setConfirm({
        title: `Queue ${plural(summary.candidates, "topic")}?`,
        body: `That adds ${summary.add.toLocaleString()} cards and brings your queue to ${summary.after.toLocaleString()} — ${(summary.after - summary.limit).toLocaleString()} over your ${summary.limit}-card limit.`,
        confirm: "Queue anyway",
        danger: true,
        onConfirm: go,
        alt: summary.laterCandidates ? { label: "Save for later", onSelect: () => act("later_matches") } : undefined,
      });
    } else go();
  };

  // What "Fill queue" would add, refreshed whenever the Later tab is open
  // and the queue changes.
  useEffect(() => {
    if (tab !== "later" || !side?.later.length) return;
    let live = true;
    call<{ plan: LaterPlan }>("later_plan").then((r) => live && setLaterPlan(r.plan));
    return () => {
      live = false;
    };
  }, [tab, side]);

  const changeScope = async (value: string) => {
    const r = await call<{ scopes: ScopeOption[]; scope: string }>("set_scope", { value });
    setScopes(r.scopes);
    setScope(r.scope);
    const open = new Set(expandedRef.current);
    if (r.scope !== "all" && r.scope !== "pinned") open.add(r.scope);
    setExpanded(open);
    await loadTree(open);
  };

  const togglePin = async (tag: string) => {
    const r = await call<{ scopes: ScopeOption[]; scope: string }>("toggle_pin", { tag });
    setScopes(r.scopes);
    setScope(r.scope);
    await loadTree();
  };

  const setOption = (key: keyof Options, value: boolean) => act("set_option", { key, value });

  /** Settings were saved: take the new numbers, colours and resource list,
   *  and redraw the tree (again once a recount lands, if one was needed). */
  const settingsSaved = (r: SettingsSaved) => {
    setOptions(r.options);
    setSide(r.side);
    setScopes(r.scopes);
    setScope(r.scope);
    applyColors(r.colors);
    if (r.recount) setRefreshing(true);
    loadTree().then(() => sync());
  };

  const doImport = async (choices: Record<string, Status>, pins: boolean) => {
    const r = await call<{ scopes: ScopeOption[]; scope: string; options: Options }>("import_colors", { choices, pins });
    setScopes(r.scopes);
    setScope(r.scope);
    setOptions(r.options);
    await loadTree();
    await sync();
  };

  /** Show a tag in the tree: leave search, widen the resource filter if
   *  it hides the tag, open its step/resource/parent folders (loading
   *  enough of a big folder to include it), then select, scroll to and
   *  flash it. */
  const reveal = async (key: string) => {
    type Located = {
      exists: boolean;
      open?: string[];
      limits?: Record<string, number>;
      inScope?: boolean;
      status?: Status;
    };
    let loc = await call<Located>("locate", { key });
    if (!loc.exists) {
      toast("That tag isn't in this collection anymore", "warn");
      return;
    }
    if (!loc.inScope) {
      const r = await call<{ scopes: ScopeOption[]; scope: string }>("set_scope", { value: "all" });
      setScopes(r.scopes);
      setScope(r.scope);
      loc = await call<Located>("locate", { key });
    }
    if (loc.status === "completed" && options?.hideCompleted) {
      await act("set_option", { key: "hideCompleted", value: false });
      toast("Showing done topics", "info");
    }
    if (queryRef.current) {
      // Leave search mode right away (the debounced effect would lag).
      queryRef.current = "";
      searchSeq.current++;
      setQuery("");
      setSearch(null);
      setSummary(null);
    }
    const open = new Set(expandedRef.current);
    for (const k of loc.open ?? []) {
      open.add(k);
      collapsedRef.current.delete(k);
    }
    await loadTree(open, loc.limits ?? {});
    setSelected(key);
    setFlash((f) => ({ key, n: f.n + 1 }));
  };

  // Context menu for a tree row.
  const menuEntries = (key: string): MenuEntry[] => {
    const n = nodes[key];
    if (!n || isGroup(n)) return [];
    const own = n.inherited ? null : n.status;
    const entries: MenuEntry[] = [];
    if (own === "queued") entries.push({ label: "Remove from queue", icon: <ListMinus size={14} />, onSelect: () => act("unqueue", { tags: [n.tag] }) });
    else
      entries.push({
        label: "Add to queue",
        icon: <ListPlus size={14} />,
        disabled: n.status === "queued",
        hint: "Space",
        onSelect: async () => warnIfOver(await act("queue", { tags: [n.tag] }), [n.tag]),
      });
    if (own === "later")
      entries.push({ label: "Remove from Later", icon: <BookmarkMinus size={14} />, hint: "s", onSelect: () => act("unlater", { tags: [n.tag] }) });
    else if (own !== "completed")
      entries.push({
        label: own === "queued" ? "Move to Later" : "Save for later",
        icon: <BookmarkPlus size={14} />,
        hint: "s",
        disabled: !!n.status && n.inherited,
        onSelect: () => act("later", { tags: [n.tag] }),
      });
    if (own !== "completed")
      entries.push({ label: options?.unsuspendOnComplete ? "Mark completed & unsuspend" : "Mark completed", icon: <CircleCheck size={14} />, onSelect: () => complete([n.tag]) });
    if (own) entries.push({ label: "Clear status", icon: <Eraser size={14} />, onSelect: () => act("clear", { tags: [n.tag] }) });
    entries.push(
      { separator: true },
      { label: "Browse cards", icon: <ExternalLink size={14} />, onSelect: () => call("browse", { tags: [n.tag] }) },
      { label: "Unsuspend cards", icon: <LockOpen size={14} />, onSelect: () => act("unsuspend", { tags: [n.tag] }) },
    );
    if (n.resource)
      entries.push(
        { separator: true },
        n.pinned
          ? { label: "Unpin", icon: <PinOff size={14} />, onSelect: () => togglePin(n.tag) }
          : { label: "Pin to top", icon: <Pin size={14} />, onSelect: () => togglePin(n.tag) },
      );
    return entries;
  };

  const words = useMemo(
    () => (search ? search.query.toLowerCase().replace(/_/g, " ").split(/\s+/).filter(Boolean) : []),
    [search],
  );
  const currentScope = scopes.find((s) => s.value === scope);
  const emptyText =
    ready && search && !search.roots.length
      ? `No topics match “${search.query}”${scope !== "all" ? ` in ${currentScope?.label ?? "this resource"}` : ""}`
      : ready && !search && !rows.length && kids[""]
        ? "No tags to show here."
        : null;

  return (
    <div className="app">
      <Header
        options={options}
        refreshing={refreshing}
        onRefresh={() => {
          setRefreshing(true);
          call("refresh");
        }}
        onImport={() => setImporting(true)}
        onSettings={() => setSettingsOpen(true)}
      />
      <div>
        {options?.banner && (
          <Banner
            onImport={() => setImporting(true)}
            onDismiss={() => call<{ options: Options }>("dismiss_banner").then((r) => setOptions(r.options))}
          />
        )}
      </div>
      <main className="main">
        <section className="panel">
          <div className="toolbar">
            <SearchBox ref={searchInput} value={query} onChange={setQuery} onSubmit={() => query.trim() && runSearch(query.trim())} />
            <ScopePicker scopes={scopes} value={scope} onChange={changeScope} />
            <HideDoneSwitch checked={hideDone} onChange={(v) => setOption("hideCompleted", v)} />
          </div>
          {search && summary && summary.count > 0 && (
            <MatchBar summary={summary} onQueueAll={queueMatches} onLaterAll={() => act("later_matches")} />
          )}
          <Tree
            rows={rows}
            nodes={nodes}
            expanded={search ? search.expanded : expanded}
            selected={selected}
            flash={flash}
            words={words}
            loading={!ready}
            emptyText={emptyText}
            onSelect={setSelected}
            onToggleExpand={toggleExpand}
            onLoadMore={loadMore}
            onToggleQueue={toggleQueue}
            onToggleLater={toggleLater}
            onContext={(key, x, y) => setMenu({ key, anchor: { x, y } })}
          />
          <DetailsBar details={details} />
        </section>
        {side && (
          <SidePanel
            side={side}
            tab={tab}
            onTab={setTab}
            laterPlan={laterPlan}
            unsuspendOnComplete={options?.unsuspendOnComplete ?? true}
            onLimit={(value) => act("set_limit", { value })}
            onComplete={complete}
            onFinishSession={finishSession}
            onUnwatch={(tag) => act("unwatch", { tags: [tag] })}
            onUnqueue={(tag) => act("unqueue", { tags: [tag] })}
            onLater={(tag) => act("later", { tags: [tag] })}
            onUnlater={(tag) => act("unlater", { tags: [tag] })}
            onQueue={async (tag) => warnIfOver(await act("queue", { tags: [tag] }), [tag])}
            onQueueMany={async (tags) => warnIfOver(await act("queue", { tags }), tags)}
            onLaterMany={(tags) => act("later", { tags })}
            onCompleteGroup={(tags, label) =>
              setConfirm({
                title: `Check off ${plural(tags.length, `${label} topic`)}?`,
                body: options?.unsuspendOnComplete
                  ? "Their suspended cards will be unsuspended so you can start reviewing them."
                  : "They'll stay in the queue as checked off until their cards are studied.",
                confirm: "Check off",
                onConfirm: () => act("complete", { tags }),
              })
            }
            onFill={() => act("fill_from_later")}
            onClear={(tag) => act("clear", { tags: [tag] })}
            onUnsuspend={() => act("unsuspend", { tags: [] })}
            onBrowse={() => call("browse", { tags: [] })}
            onReveal={reveal}
            activeKey={selected}
          />
        )}
      </main>

      {menu && <Menu anchor={menu.anchor} entries={menuEntries(menu.key)} onClose={() => setMenu(null)} minWidth={230} />}
      {confirm && <ConfirmDialog request={confirm} onClose={() => setConfirm(null)} />}
      {importing && <ImportDialog onClose={() => setImporting(false)} onImport={doImport} />}
      {settingsOpen && <SettingsDialog onClose={() => setSettingsOpen(false)} onSaved={settingsSaved} />}
      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
