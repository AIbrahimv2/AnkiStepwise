// Shapes returned by the Python bridge (src/bridge.py, src/viewmodel.py).

export type Status = "queued" | "completed" | null;
export type Check = "on" | "off" | "partial";

export interface TagNode {
  key: string;
  tag: string;
  label: string;
  fresh: number;
  total: number;
  hasKids: boolean;
  top: boolean;
  pinned: boolean;
  resource: boolean;
  check: Check;
  locked: boolean;
  status: Status;
  inherited: boolean;
  source: string | null;
  nestedQueued: number;
  progress: { done: number; total: number } | null;
  doneAt: string | null;
}

/** The "Other tags" folder at the top level (not a tag itself). */
export interface GroupNode {
  key: string;
  label: string;
  group: true;
  count: number;
  hasKids: true;
}

export type AnyNode = TagNode | GroupNode;
export const isGroup = (n: AnyNode | undefined): n is GroupNode => !!n && "group" in n;

export interface QueueRow {
  tag: string;
  key: string;
  title: string;
  path: string;
  fresh: number;
  missing: boolean;
}

export interface DoneRow {
  tag: string;
  key: string;
  title: string;
  path: string;
  date: string;
}

export interface Side {
  count: number;
  limit: number;
  over: boolean;
  unit: string;
  queued: QueueRow[];
  completed: DoneRow[];
}

export interface Summary {
  count: number;
  queued: number;
  done: number;
  candidates: number;
  add: number;
  after: number;
  limit: number;
  over: boolean;
  truncated: boolean;
}

export interface Details {
  key: string;
  title: string;
  path: string;
  fresh: number;
  total: number;
  status: Status;
  via: string | null;
  date: string | null;
  limit: number;
  add?: number;
  overlap?: number;
  after?: number;
  over?: boolean;
}

export interface ScopeOption {
  value: string;
  label: string;
  kind: "all" | "pinned" | "resource" | "other";
  pinned?: boolean;
}

export interface Options {
  unsuspendOnComplete: boolean;
  showOnDeck: boolean;
  colorSync: boolean;
  colorSyncAvailable: boolean;
  hideCompleted: boolean;
  banner: boolean;
}

export interface Boot {
  ready: boolean;
  side: Side;
  scopes: ScopeOption[];
  scope: string;
  options: Options;
  colors: { queued: string; completed: string };
}

export interface Bundle {
  side: Side;
  options: Options;
  nodes?: TagNode[];
  summary?: Summary;
  details?: Details | null;
}

export interface SearchResult {
  nodes: TagNode[];
  children: Record<string, string[]>;
  roots: string[];
  matches: string[];
  truncated: boolean;
  summary?: Summary;
}

export interface ImportGroup {
  color: string;
  count: number;
  sample: string;
  suggested: Status;
}

export type PushEvent =
  | { type: "index" }
  | { type: "sync" }
  | { type: "toast"; message: string };
