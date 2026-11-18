// What every one of AIbrahimv2's Anki add-ons shows about itself, through
// anki-addon-kit: Settings, What's new and About are tabs of the kit's own
// window (py/page.py, its page built from standalone/), whichever add-on
// opens it. An add-on's page opens it (openKitWindow) and puts a dot on its
// ⋯ menu while there's news (useKitAbout, selfOf). Don't edit a vendored
// copy (web/src/kit/ in an add-on): change it in the kit and run its
// sync.py.

import { useCallback, useEffect, useState } from "react";
import type { KitAbout, KitAddon, KitCall, KitTab } from "./types";

/** Tells every useKitAbout() on the page to fetch again (after "seen"). */
const CHANGED = "kit:changed";

export function announceKitChange(): void {
  window.dispatchEvent(new Event(CHANGED));
}

/** What the kit knows about the add-ons, refetched when it changes, and when
 *  the page gets the focus back (What's new, read in the kit's window,
 *  clears the add-on's dot). */
export function useKitAbout(call: KitCall): [KitAbout | null, () => void] {
  const [about, setAbout] = useState<KitAbout | null>(null);
  const load = useCallback(() => {
    call<{ about: KitAbout }>("about").then((r) => setAbout(r.about), () => undefined);
  }, [call]);
  useEffect(() => {
    load();
    window.addEventListener(CHANGED, load);
    window.addEventListener("focus", load);
    return () => {
      window.removeEventListener(CHANGED, load);
      window.removeEventListener("focus", load);
    };
  }, [load]);
  return [about, load];
}

/** This add-on, from useKitAbout(): `unseen` puts a dot on its About entry. */
export function selfOf(about: KitAbout | null): KitAddon | null {
  return about?.addons.find((a) => a.id === about.self) ?? null;
}

export const listingUrl = (a: KitAddon) =>
  a.ankiweb ? `https://ankiweb.net/shared/info/${a.ankiweb}` : `https://github.com/${a.github}`;

/** Shows Settings, What's new or About in the kit's own window. */
export function openKitWindow(call: KitCall, tab: KitTab): void {
  void call("page", { tab }).catch(() => undefined);
}
