import {
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
import { SidePanel } from "./components/SidePanel";
import { HideDoneSwitch, MatchBar, ScopePicker, SearchBox } from "./components/Toolbar";
import { DetailsBar, type FlatRow, Tree } from "./components/Tree";
import { type Anchor, Menu, type MenuEntry, plural } from "./components/ui";
import {
  type AnyNode,
  type Boot,
  type Bundle,
  type Details,
  type Options,
  type PushEvent,
  type ScopeOption,
  type SearchResult,
  type Side,
  type Status,
  type Summary,
  type TagNode,
  isGroup,
} from "./types";

interface SearchState {
  query: string;
  roots: string[];
  kids: Record<string, string[]>;
  expanded: Set<string>;
  matches: string[];
  truncated: boolean;
}

type NodeList = { nodes: AnyNode[] };

export function App() {
  const [ready, setReady] = useState(false);
  const [side, setSide] = useState<Side | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [scopes, setScopes] = useState<ScopeOption[]>([]);
  const [scope, setScope] = useState("all");

  const [nodes, setNodes] = useState<Record<string, AnyNode>>({});
  const [kids, setKids] = useState<Record<string, string[]>>({});
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
  const [refreshing, setRefreshing] = useState(false);

  const searchInput = useRef<HTMLInputElement>(null);
  const searchSeq = useRef(0);
  const queryRef = useRef(query);
  queryRef.current = query;
  const expandedRef = useRef(expanded);
  expandedRef.current = expanded;

  // --- toasts --------------------------------------------------------------

  const toast = useCallback((message: string, tone: Tone = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-2), { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "error" ? 6000 : 3600);
  }, []);

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
    const open = search ? search.expanded : expanded;
    const walk = (keys: string[], depth: number, parent: string | null) => {
      for (const key of keys) {
        const n = nodes[key];
        if (!n) continue;
        if (hideDone && !isGroup(n) && n.status === "completed") continue;
        out.push({ key, depth, parent });
        if (open.has(key) && kidMap[key]) walk(kidMap[key], depth + 1, key);
      }
    };
    walk(search ? search.roots : (kids[""] ?? []), 0, null);
    return out;
  }, [nodes, kids, expanded, search, hideDone]);

  // What every mutating command needs to send back a full refresh.
  const ctx = useRef({ visible: [] as string[], matches: null as string[] | null, truncated: false, selected: null as string | null });
  ctx.current = {
    visible: rows.map((r) => r.key).filter((k) => !isGroup(nodes[k])),
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
        expanded: new Set(Object.keys(r.children)),
        matches: r.matches,
        truncated: r.truncated,
      });
      setSummary(r.summary ?? null);
    },
    [mergeNodes],
  );

  /** (Re)load the browse tree: top level plus every expanded row. Pass
   *  `open` when the expanded set is changing in the same update. */
  const loadTree = useCallback(async (open?: Set<string>) => {
    const q = queryRef.current.trim();
    if (q) return runSearch(q);
    const keys = ["", ...(open ?? expandedRef.current)];
    const lists = await Promise.all(keys.map((key) => call<NodeList>("children", { key })));
    // A single resource in scope opens straight away.
    const only = lists[0].nodes.length === 1 ? lists[0].nodes[0] : null;
    if (only?.hasKids && !keys.includes(only.key)) {
      keys.push(only.key);
      lists.push(await call<NodeList>("children", { key: only.key }));
      setExpanded((e) => new Set(e).add(only.key));
    }
    mergeNodes(lists.flatMap((l) => l.nodes), false);
    setKids(Object.fromEntries(keys.map((k, i) => [k, lists[i].nodes.map((n) => n.key)])));
  }, [mergeNodes, runSearch]);

  // --- boot & pushes -------------------------------------------------------

  useEffect(() => {
    call<Boot>("boot").then((b) => {
      setSide(b.side);
      setOptions(b.options);
      setScopes(b.scopes);
      setScope(b.scope);
      const root = document.documentElement.style;
      root.setProperty("--q-raw", b.colors.queued);
      root.setProperty("--d-raw", b.colors.completed);
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
          const r = await call<NodeList>("children", { key });
          mergeNodes(r.nodes, false);
          setSearch((s) => (s ? { ...s, kids: { ...s.kids, [key]: r.nodes.map((n) => n.key) }, expanded: open } : s));
        } else {
          setSearch((s) => (s ? { ...s, expanded: open } : s));
        }
        return;
      }
      if (expandedRef.current.has(key)) {
        setExpanded((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
        return;
      }
      const r = await call<NodeList>("children", { key });
      mergeNodes(r.nodes, false);
      setKids((k) => ({ ...k, [key]: r.nodes.map((n) => n.key) }));
      setExpanded((prev) => new Set(prev).add(key));
    },
    [search, mergeNodes],
  );

  const warnIfOver = useCallback(
    (b: Bundle) => {
      if (b.side.over) toast(`${(b.side.count - b.side.limit).toLocaleString()} over your ${b.side.limit}-card limit`, "warn");
    },
    [toast],
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
        warnIfOver(await act("queue", { tags: [n.tag] }));
      }
    },
    [act, toast, warnIfOver],
  );

  const complete = useCallback((tags: string[]) => act("complete", { tags }), [act]);

  const completeAll = () => {
    const n = side?.queued.length ?? 0;
    if (!n) return;
    setConfirm({
      title: `Mark ${plural(n, "topic")} completed?`,
      body: options?.unsuspendOnComplete
        ? "Their suspended cards will be unsuspended so you can start reviewing them."
        : "They'll move to your Completed list.",
      confirm: "Complete all",
      onConfirm: () => act("complete", { tags: [] }),
    });
  };

  const queueMatches = () => {
    if (!summary) return;
    const go = () => act("queue_matches");
    if (summary.over) {
      setConfirm({
        title: `Queue ${plural(summary.candidates, "topic")}?`,
        body: `That adds ${summary.add.toLocaleString()} new cards and brings your queue to ${summary.after.toLocaleString()} — ${(summary.after - summary.limit).toLocaleString()} over your ${summary.limit}-card limit.`,
        confirm: "Queue anyway",
        danger: true,
        onConfirm: go,
      });
    } else go();
  };

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

  const doImport = async (choices: Record<string, Status>, pins: boolean) => {
    const r = await call<{ scopes: ScopeOption[]; scope: string; options: Options }>("import_colors", { choices, pins });
    setScopes(r.scopes);
    setScope(r.scope);
    setOptions(r.options);
    await loadTree();
    await sync();
  };

  const reveal = async (key: string) => {
    // Double-click a queue row: find it in the tree via search.
    const n = nodes[key];
    const label = n && !isGroup(n) ? n.label : key.split("::").pop()?.replace(/_/g, " ") ?? key;
    setQuery(label.replace(/^#/, ""));
    setSelected(key);
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
        onSelect: async () => warnIfOver(await act("queue", { tags: [n.tag] })),
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
        onOption={setOption}
        onEditConfig={() => call("edit_config")}
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
          {search && summary && summary.count > 0 && <MatchBar summary={summary} onQueueAll={queueMatches} />}
          <Tree
            rows={rows}
            nodes={nodes}
            expanded={search ? search.expanded : expanded}
            selected={selected}
            words={words}
            loading={!ready}
            emptyText={emptyText}
            onSelect={setSelected}
            onToggleExpand={toggleExpand}
            onToggleQueue={toggleQueue}
            onContext={(key, x, y) => setMenu({ key, anchor: { x, y } })}
          />
          <DetailsBar details={details} searching={!!search} />
        </section>
        {side && (
          <SidePanel
            side={side}
            unsuspendOnComplete={options?.unsuspendOnComplete ?? true}
            onLimit={(value) => act("set_limit", { value })}
            onComplete={complete}
            onCompleteAll={completeAll}
            onUnqueue={(tag) => act("unqueue", { tags: [tag] })}
            onRequeue={async (tag) => warnIfOver(await act("queue", { tags: [tag] }))}
            onClear={(tag) => act("clear", { tags: [tag] })}
            onUnsuspend={() => act("unsuspend", { tags: [] })}
            onBrowse={() => call("browse", { tags: [] })}
            onReveal={reveal}
          />
        )}
      </main>

      {menu && <Menu anchor={menu.anchor} entries={menuEntries(menu.key)} onClose={() => setMenu(null)} minWidth={230} />}
      {confirm && <ConfirmDialog request={confirm} onClose={() => setConfirm(null)} />}
      {importing && <ImportDialog onClose={() => setImporting(false)} onImport={doImport} />}
      <Toasts toasts={toasts} />
    </div>
  );
}
