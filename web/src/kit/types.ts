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
  /** Where its settings live: a tab of the kit's window, drawn from a
   *  schema ("page") or by the add-on's own panel ("hosted"); in its own
   *  window ("window", an older copy of the add-on, opened by the
   *  "open_settings" command); or nowhere (null). */
  settings: "window" | "page" | "hosted" | null;
  changes: KitRelease[];
}

export interface KitAbout {
  self: string;
  /** `name` is the GitHub handle; `fullName`, if given, signs About; the
   *  signature opens `website`; and `socials` are linked under it (LinkedIn
   *  and Instagram get their icons). */
  author: {
    name: string;
    github: string;
    fullName?: string;
    website?: string;
    socials?: { name: string; url: string }[];
  };
  addons: KitAddon[];
}

export type KitTab = "settings" | "news" | "about";

/** Sends one of the kit's commands through the add-on's own bridge, as
 *  `{cmd: "kit", op, ...args}`. */
export type KitCall = <T = Record<string, unknown>>(op: string, args?: Record<string, unknown>) => Promise<T>;

/** What an add-on's own Settings panel gets from the kit's window. */
export interface KitSettingsHost {
  /** Closes the window. */
  close(): void;
}

/** An add-on's Settings panel, as its script hands it to the kit's window
 *  (provideSettings, in hosted.tsx). */
export interface KitSettingsPanel {
  id: string;
  /** Draws the panel in `el`; returns how to take it away. */
  mount(el: HTMLElement, host: KitSettingsHost): () => void;
}

declare global {
  interface Window {
    kitSettings?: KitSettingsPanel;
  }
}

/** Sent on window when a panel has been provided. */
export const KIT_SETTINGS_EVENT = "kit:settings";
