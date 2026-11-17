// What every one of AIbrahimv2's Anki add-ons shows about itself, through
// anki-addon-kit. What's new and About open in the kit's own window
// (py/page.py, its page built from standalone/); an add-on with a page of its
// own shows its Settings here, in a dialog over that page. Styled by
// dialog.css. Don't edit a vendored copy (web/src/kit/ in an add-on): change
// it in the kit and run its sync.py.

import { Info, Sparkles, X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { IconButton, Modal } from "./controls";
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

/** Shows What's new or About in the kit's own window. */
export function openKitWindow(call: KitCall, tab: KitTab): void {
  void call("page", { tab }).catch(() => undefined);
}

// --- the Settings dialog -------------------------------------------------------------

export interface AddonDialogProps {
  call: KitCall;
  /** "settings" shows the dialog; "news" and "about" open the kit's window
   *  instead, and close this. */
  tab: KitTab;
  /** Kept for add-ons written for the old tabbed dialog; not used. */
  onTab?: (tab: KitTab) => void;
  /** The add-on's own settings. */
  settings?: ReactNode;
  /** Buttons under the settings (Cancel, Save...), kept in view. */
  settingsFooter?: ReactNode;
  onClose: () => void;
}

/** The add-on's Settings, in a dialog over its own page, with What's new and
 *  About a click away in the kit's window. */
export function AddonDialog(props: AddonDialogProps) {
  const { call, tab } = props;
  const [about] = useKitAbout(call);
  const self = selfOf(about);

  // What's new and About (or Settings, for an add-on without any) are in
  // the kit's window now: open it there, once, and get out of the way.
  const elsewhere = tab !== "settings" || !props.settings;
  const handedOff = useRef(false);
  const onClose = useRef(props.onClose);
  onClose.current = props.onClose;
  useEffect(() => {
    if (!elsewhere || handedOff.current) return;
    handedOff.current = true;
    openKitWindow(call, tab === "settings" ? "news" : tab);
    onClose.current();
  }, [elsewhere, call, tab]);
  if (elsewhere) return null;

  return (
    <Modal onClose={props.onClose} width={620} className="kit-modal">
      <div className="kit-panel">
        <header className="kit-head">
          <span className="kit-tile" aria-hidden="true">{self?.emoji ?? ""}</span>
          <div className="kit-title">
            <h2>Settings</h2>
            {self ? (
              <div className="kit-tagline">
                {self.name}
                {self.version && ` ${self.version}`}
              </div>
            ) : (
              <div className="skeleton" style={{ width: 90, height: 12, marginTop: 4 }} />
            )}
          </div>
          <div className="kit-head-links">
            <button type="button" className="btn ghost sm" onClick={() => openKitWindow(call, "news")}>
              <Sparkles size={14} /> What's new
              {self?.unseen && <span className="kit-dot" aria-label="new" />}
            </button>
            <button type="button" className="btn ghost sm" onClick={() => openKitWindow(call, "about")}>
              <Info size={14} /> About
            </button>
          </div>
          <IconButton size="sm" label="Close" onClick={props.onClose}>
            <X size={15} />
          </IconButton>
        </header>

        <div className="kit-body">{props.settings}</div>

        {props.settingsFooter && <div className="kit-foot">{props.settingsFooter}</div>}
      </div>
    </Modal>
  );
}
