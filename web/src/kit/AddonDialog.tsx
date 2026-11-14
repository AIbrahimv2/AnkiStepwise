// The Settings, What's new and About dialog that every one of AIbrahimv2's
// Anki add-ons shows, through anki-addon-kit. The add-on supplies its own
// Settings tab; What's new comes from its changelog and About lists the
// other add-ons, with their versions, updates and an Install button. Styled
// by dialog.css. Don't edit a vendored copy (web/src/kit/ in an add-on):
// change it in the kit and run its sync.py.

import { Bug, Check, Code2, ExternalLink, LoaderCircle, Settings2, Star, X } from "lucide-react";
import { type CSSProperties, type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { IconButton, Modal } from "./controls";
import { Inline } from "./markdown";
import { Row, Section } from "./settings";
import type { KitAbout, KitAddon, KitCall, KitRelease, KitTab, KitUpdate } from "./types";

/** Tells every useKitAbout() on the page to fetch again (after "seen"). */
const CHANGED = "kit:changed";

/** What the kit knows about the add-ons, refetched when it changes. */
export function useKitAbout(call: KitCall): [KitAbout | null, () => void] {
  const [about, setAbout] = useState<KitAbout | null>(null);
  const load = useCallback(() => {
    call<{ about: KitAbout }>("about").then((r) => setAbout(r.about), () => undefined);
  }, [call]);
  useEffect(() => {
    load();
    window.addEventListener(CHANGED, load);
    return () => window.removeEventListener(CHANGED, load);
  }, [load]);
  return [about, load];
}

/** This add-on, from useKitAbout(): `unseen` puts a dot on its About entry. */
export function selfOf(about: KitAbout | null): KitAddon | null {
  return about?.addons.find((a) => a.id === about.self) ?? null;
}

export const listingUrl = (a: KitAddon) =>
  a.ankiweb ? `https://ankiweb.net/shared/info/${a.ankiweb}` : `https://github.com/${a.github}`;

// --- the dialog ------------------------------------------------------------------

export interface AddonPanelProps {
  call: KitCall;
  tab: KitTab;
  onTab: (tab: KitTab) => void;
  /** The add-on's own settings. Leave out for an add-on without any. */
  settings?: ReactNode;
  /** Buttons under the settings (Cancel, Save...), kept in view. */
  settingsFooter?: ReactNode;
  onClose?: () => void;
  /** Settings that live elsewhere (another add-on's window): a button in
   *  the header opens them. */
  onOpenSettings?: () => void;
}

/** In a dialog over the add-on's own page. */
export function AddonDialog(props: AddonPanelProps & { onClose: () => void }) {
  return (
    <Modal onClose={props.onClose} width={600} className="kit-modal">
      <AddonPanel {...props} />
    </Modal>
  );
}

export function AddonPanel(props: AddonPanelProps) {
  const { call } = props;
  const [about, reload] = useKitAbout(call);
  const self = selfOf(about);
  const open = useCallback((url: string) => void call("open", { url }).catch(() => undefined), [call]);

  const tabs: { id: KitTab; label: string; dot?: boolean }[] = [
    ...(props.settings ? [{ id: "settings" as const, label: "Settings" }] : []),
    { id: "news", label: "What's new", dot: !!self?.unseen },
    { id: "about", label: "About" },
  ];
  const tab = tabs.some((t) => t.id === props.tab) ? props.tab : tabs[0].id;

  // Versions that were new when the dialog opened keep their badge after
  // What's new marks them read.
  const [newAtOpen, setNewAtOpen] = useState<{ id: string; versions: Set<string> } | null>(null);
  useEffect(() => {
    if (self && newAtOpen?.id !== self.id)
      setNewAtOpen({ id: self.id, versions: new Set(self.changes.filter((r) => r.isNew && r.version).map((r) => r.version!)) });
  }, [self, newAtOpen?.id]);
  const index = tabs.findIndex((t) => t.id === tab);

  // Opening What's new marks it read, for this add-on's dot and the notice.
  // Only when it was asked for: not while it stands in for a tab that
  // hasn't loaded yet.
  useEffect(() => {
    if (props.tab !== "news" || !self?.unseen) return;
    call("seen", { id: self.id }).then(() => window.dispatchEvent(new Event(CHANGED)), () => undefined);
  }, [props.tab, self?.id, self?.unseen, call]);

  return (
    <div className="kit-panel">
      <header className="kit-head">
        <span className="kit-tile" aria-hidden="true">{self?.emoji ?? ""}</span>
        <div className="kit-title">
          {self ? (
            <>
              <h2>
                {self.name}
                {self.version && <span className="kit-version">{self.version}</span>}
              </h2>
              <div className="kit-tagline">{self.tagline}</div>
            </>
          ) : (
            <div className="skeleton" style={{ width: 180, height: 14 }} />
          )}
        </div>
        {props.onOpenSettings && (
          <button type="button" className="btn sm" onClick={props.onOpenSettings}>
            <Settings2 size={14} /> Settings
          </button>
        )}
        {props.onClose && (
          <IconButton size="sm" label="Close" onClick={props.onClose}>
            <X size={15} />
          </IconButton>
        )}
      </header>

      <div className="kit-tabs" role="tablist" style={{ "--tabs": tabs.length, "--i": index } as CSSProperties}>
        <span className="thumb" aria-hidden="true" />
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={t.id === tab}
            className={t.id === tab ? "active" : ""}
            onClick={() => props.onTab(t.id)}
          >
            {t.label}
            {t.dot && <span className="kit-dot" aria-label="new" />}
          </button>
        ))}
      </div>

      <div className="kit-body" role="tabpanel">
        {tab === "settings" && props.settings}
        {tab === "news" && (self ? <WhatsNew addon={self} wasNew={newAtOpen?.versions} onLink={open} /> : <Loading />)}
        {tab === "about" && (about && self ? <AboutTab about={about} self={self} call={call} onLink={open} reload={reload} /> : <Loading />)}
      </div>

      {tab === "settings" && props.settingsFooter && <div className="kit-foot">{props.settingsFooter}</div>}
    </div>
  );
}

function Loading() {
  return <div className="skeleton" style={{ height: 220, borderRadius: 12 }} />;
}

// --- what's new ----------------------------------------------------------------------

const SHOWN = 3;

function WhatsNew(props: { addon: KitAddon; wasNew?: Set<string>; onLink: (url: string) => void }) {
  const [all, setAll] = useState(false);
  const releases = props.addon.changes.filter((r) => r.sections.some((s) => s.items.length));
  if (!releases.length) return <div className="kit-empty">No changes are listed yet.</div>;
  const shown = all ? releases : releases.slice(0, SHOWN);
  const older = releases.length - shown.length;
  return (
    <div className="kit-releases">
      {shown.map((r, i) => (
        <Release
          key={r.version ?? `next-${i}`}
          release={{ ...r, isNew: r.isNew || (!!r.version && !!props.wasNew?.has(r.version)) }}
          onLink={props.onLink}
        />
      ))}
      {older > 0 && (
        <button type="button" className="btn ghost sm kit-more" onClick={() => setAll(true)}>
          Show {older} older {older === 1 ? "version" : "versions"}
        </button>
      )}
    </div>
  );
}

function Release(props: { release: KitRelease; onLink: (url: string) => void }) {
  const r = props.release;
  return (
    <article className="kit-release">
      <header>
        <span className="kit-ver">{r.version ? `Version ${r.version}` : "Not released yet"}</span>
        {r.date && <span className="kit-date">{formatDate(r.date)}</span>}
        {r.isNew && <span className="kit-badge">New</span>}
      </header>
      {r.sections
        .filter((s) => s.items.length)
        .map((s, i) => (
          <div className="kit-rsec" key={i}>
            {s.title && <h4>{s.title}</h4>}
            <ul>
              {s.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} onLink={props.onLink} />
                </li>
              ))}
            </ul>
          </div>
        ))}
    </article>
  );
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// --- about -------------------------------------------------------------------------

/** Asks AnkiWeb (through Anki's own update check) once per opening, and
 *  waits for the answer by asking again. */
function useUpdates(call: KitCall): Record<string, KitUpdate> | null {
  const [updates, setUpdates] = useState<Record<string, KitUpdate> | null>(null);
  useEffect(() => {
    let alive = true;
    let tries = 0;
    const ask = () =>
      call<{ done: boolean; updates: Record<string, KitUpdate> }>("updates").then(
        (r) => {
          if (!alive) return;
          if (r.done) setUpdates(r.updates);
          else if (++tries < 40) setTimeout(ask, 500);
          else setUpdates({});
        },
        () => alive && setUpdates({}),
      );
    ask();
    return () => {
      alive = false;
    };
  }, [call]);
  return updates;
}

function AboutTab(props: {
  about: KitAbout;
  self: KitAddon;
  call: KitCall;
  onLink: (url: string) => void;
  reload: () => void;
}) {
  const { about, self, call, onLink } = props;
  const updates = useUpdates(call);
  const [installing, setInstalling] = useState<Set<string>>(new Set());

  // While an install runs, look again now and then: Anki says when it's
  // done, and the row then asks for a restart.
  const reload = useRef(props.reload);
  reload.current = props.reload;
  useEffect(() => {
    if (!installing.size) return;
    const t = setInterval(() => reload.current(), 1500);
    return () => clearInterval(t);
  }, [installing.size]);
  useEffect(() => {
    const done = [...installing].filter((id) => about.addons.find((a) => a.id === id)?.installed && updates?.[id] !== "available");
    if (done.length) setInstalling((s) => new Set([...s].filter((id) => !done.includes(id))));
  }, [about, installing, updates]);

  const install = (a: KitAddon) => {
    setInstalling((s) => new Set(s).add(a.id));
    call("install", { id: a.id }).catch(() =>
      setInstalling((s) => {
        const next = new Set(s);
        next.delete(a.id);
        return next;
      }),
    );
  };

  const others = about.addons.filter((a) => a.id !== self.id && (a.installed || a.ankiweb));
  const status = updates?.[self.id];

  return (
    <div className="kit-about">
      <p className="kit-about-text">{self.about}</p>
      <div className="kit-links">
        <button type="button" className="btn sm" onClick={() => onLink(`https://github.com/${self.github}`)}>
          <Code2 size={14} /> Source code
        </button>
        <button type="button" className="btn sm" onClick={() => onLink(`https://github.com/${self.github}/issues`)}>
          <Bug size={14} /> Report a problem
        </button>
        {self.ankiweb && (
          <button type="button" className="btn sm" onClick={() => onLink(`https://ankiweb.net/shared/info/${self.ankiweb}`)}>
            <Star size={14} /> Rate it on AnkiWeb
          </button>
        )}
      </div>

      <div className="settings">
        <Section title="This add-on">
          <Row
            label={self.version ? `Version ${self.version}` : "Not released yet"}
            hint={
              self.dev
                ? "Runs from its own folder rather than from AnkiWeb, so Anki doesn't update it."
                : status === undefined
                  ? "Checking AnkiWeb for updates…"
                  : status === "available"
                    ? "A newer version is on AnkiWeb."
                    : status === "current"
                      ? "Up to date."
                      : "Couldn't reach AnkiWeb to check for updates."
            }
          >
            {status === "available" &&
              (installing.has(self.id) ? (
                <Busy label="Updating…" />
              ) : (
                <button type="button" className="btn sm primary" onClick={() => install(self)}>
                  Update
                </button>
              ))}
            {status === "current" && !self.dev && (
              <span className="kit-status ok">
                <Check size={14} strokeWidth={2.5} /> Up to date
              </span>
            )}
          </Row>
        </Section>

        {others.length > 0 && (
          <Section title={`More add-ons by ${about.author.name}`}>
            {others.map((a) => (
              <div className="set-row kit-addon" key={a.id}>
                <span className="kit-tile sm" aria-hidden="true">{a.emoji}</span>
                <div className="set-text">
                  <div className="set-label">
                    <button type="button" className="kit-name" onClick={() => onLink(listingUrl(a))} title="Open its page">
                      {a.name}
                      {a.unseen && <span className="kit-dot" aria-label="updated" />}
                      <ExternalLink size={11} />
                    </button>
                  </div>
                  <div className="set-hint">{a.tagline}</div>
                </div>
                <div className="set-control">
                  <AddonStatus
                    addon={a}
                    update={updates?.[a.id]}
                    installing={installing.has(a.id)}
                    onInstall={() => install(a)}
                    onNews={() => void call("page", { id: a.id, tab: "news" }).catch(() => undefined)}
                  />
                </div>
              </div>
            ))}
          </Section>
        )}
      </div>
    </div>
  );
}

function AddonStatus(props: {
  addon: KitAddon;
  update: KitUpdate | undefined;
  installing: boolean;
  onInstall: () => void;
  onNews: () => void;
}) {
  const a = props.addon;
  if (props.installing) return <Busy label={a.installed ? "Updating…" : "Installing…"} />;
  if (!a.installed) {
    if (!a.supported) return <span className="kit-status">macOS only</span>;
    return (
      <button type="button" className="btn sm" onClick={props.onInstall}>
        Install
      </button>
    );
  }
  if (!a.enabled) return <span className="kit-status">Turned off</span>;
  if (!a.running) return <span className="kit-status">Restart Anki to start it</span>;
  if (props.update === "available")
    return (
      <button type="button" className="btn sm" onClick={props.onInstall}>
        Update
      </button>
    );
  if (a.unseen)
    return (
      <button type="button" className="btn ghost sm" onClick={props.onNews}>
        What's new
      </button>
    );
  return (
    <span className="kit-status ok">
      <Check size={14} strokeWidth={2.5} /> Installed
    </span>
  );
}

function Busy(props: { label: string }) {
  return (
    <span className="kit-status">
      <LoaderCircle size={14} className="spin" /> {props.label}
    </span>
  );
}
