// What the kit's Python side (kit/family.py) tells the page about
// AIbrahimv2's add-ons. Don't edit a vendored copy (web/src/kit/ in an
// add-on): change it in the kit and run its sync.py.

export interface KitRelease {
  /** "1.2.0", or null for changes not released yet. */
  version: string | null;
  /** ISO date, when the changelog gives one. */
  date: string | null;
  sections: { title: string; items: string[] }[];
  /** Released after the version you last saw. */
  isNew: boolean;
}

export type KitUpdate = "available" | "current" | "dev" | "unknown";

export interface KitAddon {
  id: string;
  name: string;
  emoji: string;
  tagline: string;
  about: string;
  ankiweb: number | null;
  github: string;
  /** Installed, in any form (from AnkiWeb, a file or a linked repo). */
  installed: boolean;
  /** Installed and not turned off in Tools → Add-ons. */
  enabled: boolean;
  /** Loaded this session. Installed and enabled but not running means it
   *  was just installed: Anki needs a restart. */
  running: boolean;
  /** Runs from a folder that isn't AnkiWeb's (a linked repo, say). */
  dev: boolean;
  /** Works on this computer (AnkiGlass and AnkiBare are macOS only). */
  supported: boolean;
  version: string | null;
  /** Updated since you last opened its What's new. */
  unseen: boolean;
  /** Where its settings live: in its own window ("window", opened by the
   *  "open_settings" command), in the kit's page ("page", described by a
   *  schema), or nowhere (null). */
  settings: "window" | "page" | null;
  changes: KitRelease[];
}

export interface KitAbout {
  self: string;
  author: { name: string; github: string };
  addons: KitAddon[];
}

export type KitTab = "settings" | "news" | "about";

/** Sends one of the kit's commands through the add-on's own bridge, as
 *  `{cmd: "kit", op, ...args}`. */
export type KitCall = <T = Record<string, unknown>>(op: string, args?: Record<string, unknown>) => Promise<T>;
