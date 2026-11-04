// Shapes returned by the Python bridge (src/bridge.py, src/viewmodel.py).

export type Status = "queued" | "completed" | "later" | null;
export type Check = "on" | "off" | "partial";

export interface TagNode {
  key: string;
  tag: string;
  label: string;
  /** What counts toward the limit (suspended cards by default). */
  fresh: number;
  suspended: number;
  /** Unsuspended but never studied: new in Anki's queue, or buried. */
  waiting: number;
  /** The buried part of `waiting`; comes back by itself. */
  buried: number;
  total: number;
  hasKids: boolean;
  top: boolean;
  pinned: boolean;
  resource: boolean;
  /** "Step 1" etc. for resource-level rows under a resource root. */
  step: string | null;
  stepIndex: number | null;
  check: Check;
  locked: boolean;
  status: Status;
  inherited: boolean;
  source: string | null;
  nestedQueued: number;
  nestedLater: number;
  progress: { done: number; total: number } | null;
  /** When the (own or inherited) status was set, e.g. "Nov 4". */
  since: string | null;
}

/** A section header in the tree: a step ("Step 1", holding its resources)
 *  or the "Other tags" folder. Not a tag itself, so it can't be queued. */
export interface GroupNode {
  key: string;
  label: string;
  group: true;
  kind: "root" | "other";
  sub?: string;
  count: number;
  hasKids: true;
  fresh?: number;
  suspended?: number;
  waiting?: number;
  buried?: number;
  total?: number;
  progress?: { done: number; total: number } | null;
  stepIndex?: number;
}

export type AnyNode = TagNode | GroupNode;
export const isGroup = (n: AnyNode | undefined): n is GroupNode => !!n && "group" in n;

interface RowBase {
  tag: string;
  key: string;
  title: string;
  path: string;
  step: string | null;
  stepIndex: number | null;
}

export interface QueueRow extends RowBase {
  fresh: number;
  waiting: number;
  buried: number;
  missing: boolean;
}

export interface LaterRow extends QueueRow {
  date: string;
}

export interface DoneRow extends RowBase {
  date: string;
}

export type CountMode = "suspended" | "new" | "all";

export interface Side {
  count: number;
  limit: number;
  over: boolean;
  mode: CountMode;
  unit: string;
  queued: QueueRow[];
  later: LaterRow[];
  completed: DoneRow[];
}

export interface LaterPlan {
  picked: number;
  add: number;
  after: number;
  skipped: number;
  limit?: number;
}

export interface Summary {
  count: number;
  queued: number;
  done: number;
  later: number;
  candidates: number;
  laterCandidates: number;
  add: number;
  after: number;
  limit: number;
  over: boolean;
  truncated: boolean;
}

export interface Details {
  key: string;
  tag: string;
  title: string;
  path: string;
  step: string | null;
  stepIndex: number | null;
  fresh: number;
  suspended: number;
  waiting: number;
  buried: number;
  total: number;
  mode: CountMode;
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
  /** Full label for the picker button, e.g. "B&B · Step 1". */
  label: string;
  /** Label inside the list, under its step's section. */
  short?: string;
  kind: "all" | "pinned" | "root" | "resource" | "other";
  group?: string;
  stepIndex?: number;
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
  colors: { queued: string; completed: string; later: string };
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
