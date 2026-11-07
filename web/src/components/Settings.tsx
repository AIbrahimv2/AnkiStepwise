import { Plus, X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { call } from "../bridge";
import type { CountMode, PinnedResource, Settings, SettingsSaved, SettingsValues, StatusColors } from "../types";
import { StepChip } from "./Tree";
import { IconButton, Modal, Switch } from "./ui";

const LIMIT_MIN = 1;
const LIMIT_MAX = 5000;

const MODES: { value: CountMode; label: string; hint: string }[] = [
  {
    value: "new",
    label: "New cards",
    hint:
      "New cards Anki will show you today, suspended or not. With Bury new siblings on (deck options), a note counts once. Checking a topic off doesn't change it; studying does.",
  },
  { value: "suspended", label: "To unsuspend", hint: "Only cards that are still suspended." },
  { value: "all", label: "All cards", hint: "Every card under the topic, studied or not." },
];

// Colorful Tags' palette. A native colour picker (<input type="color">)
// would open a macOS panel from the web view, which can crash Anki, so
// colours are picked from swatches or typed as hex.
const PALETTE = ["#ff9300", "#00f900", "#af52de", "#ff2600", "#0096ff", "#fefb00", "#ff40ff", "#00fdff", "#929292"];
const HEX = /^#[0-9a-f]{6}$/i;

const COLOR_ROWS: { key: keyof StatusColors; label: string }[] = [
  { key: "queued", label: "Queued" },
  { key: "completed", label: "Done" },
  { key: "later", label: "Later" },
];

/** Settings for the add-on, edited here rather than as JSON in Anki's
 *  config editor (Anki's Config button opens this too). Changes apply on
 *  Save. */
export function SettingsDialog(props: { onClose: () => void; onSaved: (r: SettingsSaved) => void }) {
  const [loaded, setLoaded] = useState<Settings | null>(null);
  const [v, setV] = useState<SettingsValues | null>(null);
  const [limitText, setLimitText] = useState("");
  const [pinned, setPinned] = useState<PinnedResource[]>([]);
  const [matches, setMatches] = useState<(string[] | null)[]>([]);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    call<{ settings: Settings }>("settings").then((r) => {
      setLoaded(r.settings);
      setV(pick(r.settings));
      setLimitText(String(r.settings.cardLimit));
      setPinned(r.settings.pinned);
    });
  }, []);

  // Which top-level tags each resource-folder pattern picks up.
  const roots = v?.resourceRoots;
  useEffect(() => {
    if (!roots) return;
    const t = setTimeout(() => {
      call<{ matches: (string[] | null)[] }>("root_matches", { patterns: roots })
        .then((r) => setMatches(r.matches))
        .catch(() => undefined);
    }, 200);
    return () => clearTimeout(t);
  }, [roots]);

  const limit = Number(limitText);
  const limitOk = /^\d+$/.test(limitText.trim()) && limit >= LIMIT_MIN && limit <= LIMIT_MAX;
  const colorsOk = v ? COLOR_ROWS.every((c) => HEX.test(v.colors[c.key])) : false;
  const current = v ? { ...v, cardLimit: limitOk ? limit : v.cardLimit, resourceRoots: cleanRoots(v.resourceRoots) } : null;
  const dirty = useMemo(() => {
    if (!loaded || !current) return false;
    return (
      JSON.stringify(current) !== JSON.stringify({ ...pick(loaded), resourceRoots: cleanRoots(loaded.resourceRoots) }) ||
      pinned.length !== loaded.pinned.length
    );
  }, [loaded, current, pinned]);

  if (!loaded || !v) {
    return (
      <Modal onClose={props.onClose} width={600}>
        <h2>Settings</h2>
        <div className="skeleton" style={{ height: 320, borderRadius: 12, marginTop: 16 }} />
      </Modal>
    );
  }

  const set = <K extends keyof SettingsValues>(key: K, value: SettingsValues[K]) => {
    setV({ ...v, [key]: value });
    setProblems(({ [key]: _gone, ...rest }) => rest);
  };
  const setColor = (key: keyof StatusColors, value: string) => {
    setV({ ...v, colors: { ...v.colors, [key]: value } });
    setProblems(({ [`colors.${key}`]: _gone, ...rest }) => rest);
  };
  const setRoot = (i: number, value: string) =>
    set(
      "resourceRoots",
      v.resourceRoots.map((p, j) => (j === i ? value : p)),
    );

  const save = async () => {
    if (!current) return;
    setSaving(true);
    try {
      const r = await call<SettingsSaved & { problems?: Record<string, string> }>("save_settings", {
        settings: { ...current, pinned: pinned.map((p) => p.tag) },
      });
      if (r.problems) setProblems(r.problems);
      else {
        props.onSaved(r);
        props.onClose();
      }
    } finally {
      setSaving(false);
    }
  };

  const mode = MODES.find((m) => m.value === v.countMode) ?? MODES[0];
  const d = loaded.defaults;

  return (
    <Modal onClose={props.onClose} width={600}>
      <h2>Settings</h2>
      <div className="settings">
        <Section title="Daily plan">
          <Row
            label="Daily limit"
            hint="The most new cards to plan for one day. The meter turns red past it."
            problem={!limitOk ? `Enter a number from ${LIMIT_MIN} to ${LIMIT_MAX.toLocaleString()}.` : problems.cardLimit}
          >
            <input
              className={`set-input num${limitOk ? "" : " bad"}`}
              inputMode="numeric"
              value={limitText}
              onChange={(e) => setLimitText(e.target.value)}
              aria-label="Daily limit"
            />
          </Row>
          <Row label="Count toward the limit" hint={mode.hint} problem={problems.countMode}>
            <div className="mini-seg">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  className={v.countMode === m.value ? "active" : ""}
                  onClick={() => set("countMode", m.value)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </Row>
          <Row label="Unsuspend when you check a topic off" hint="Checking a topic off in the queue unsuspends its cards.">
            <Switch checked={v.unsuspendOnComplete} label="" onChange={(x) => set("unsuspendOnComplete", x)} />
          </Row>
        </Section>

        <Section title="Tag tree">
          <Block
            label="Resource folders"
            hint="Top-level tags whose children are listed as resources, one step each. * matches anything."
          >
            <div className="root-list">
              {v.resourceRoots.map((p, i) => {
                const m = matches[i];
                return (
                  <div className="root-item" key={i}>
                    <input
                      className="set-input mono"
                      value={p}
                      placeholder="#AK_Step*"
                      onChange={(e) => setRoot(i, e.target.value)}
                      aria-label={`Resource folder pattern ${i + 1}`}
                    />
                    <IconButton
                      size="sm"
                      tone="bad"
                      label="Remove this pattern"
                      onClick={() =>
                        set(
                          "resourceRoots",
                          v.resourceRoots.filter((_, j) => j !== i),
                        )
                      }
                    >
                      <X size={15} />
                    </IconButton>
                    {p.trim() && m && (
                      <div className={`root-matches${m.length ? "" : " none"}`}>
                        {m.length ? `Matches ${m.join(", ")}` : "No top-level tag matches this"}
                      </div>
                    )}
                  </div>
                );
              })}
              <div>
                <button type="button" className="btn ghost sm" onClick={() => set("resourceRoots", [...v.resourceRoots, ""])}>
                  <Plus size={14} /> Add pattern
                </button>
              </div>
            </div>
          </Block>
          <Block label="Pinned resources" hint="Listed first in the resource picker. Right-click a resource in the tree to pin it.">
            {pinned.length ? (
              <div className="pin-list">
                {pinned.map((p) => (
                  <span className="pin-chip" key={p.tag} title={p.tag}>
                    {p.label}
                    {p.step && <StepChip step={p.step} index={p.stepIndex} />}
                    <IconButton size="sm" tone="bad" label={`Unpin ${p.label}`} onClick={() => setPinned(pinned.filter((x) => x.tag !== p.tag))}>
                      <X size={13} />
                    </IconButton>
                  </span>
                ))}
              </div>
            ) : (
              <div className="set-empty">Nothing pinned yet.</div>
            )}
          </Block>
        </Section>

        <Section title="Anki">
          <Row label="Meter on the deck screen" hint="A small queue meter under your deck list. Click it to open Tag Queue.">
            <Switch checked={v.showOnDeck} label="" onChange={(x) => set("showOnDeck", x)} />
          </Row>
          <Row label="Shortcut" hint="Opens Tag Queue from Anki's main window." problem={problems.shortcut}>
            <ShortcutField value={v.shortcut} onChange={(s) => set("shortcut", s)} />
          </Row>
        </Section>

        <Section title="Colours">
          <Row
            label="Colour tags in the Browser sidebar"
            hint={
              loaded.colorSyncAvailable
                ? "Keeps Colorful Tags' sidebar colours in step with each topic's status."
                : "Needs the Colorful Tags add-on."
            }
          >
            <Switch
              checked={v.colorSync && loaded.colorSyncAvailable}
              label=""
              onChange={(x) => loaded.colorSyncAvailable && set("colorSync", x)}
            />
          </Row>
          {COLOR_ROWS.map((c) => (
            <Row key={c.key} label={c.label} problem={problems[`colors.${c.key}`]}>
              <div className="swatches">
                {PALETTE.map((hex) => (
                  <button
                    key={hex}
                    type="button"
                    className={`swatch-btn${v.colors[c.key].toLowerCase() === hex ? " on" : ""}`}
                    style={{ background: hex }}
                    aria-label={hex}
                    title={hex}
                    onClick={() => setColor(c.key, hex)}
                  />
                ))}
              </div>
              <input
                className={`set-input hex${HEX.test(v.colors[c.key]) ? "" : " bad"}`}
                value={v.colors[c.key]}
                onChange={(e) => setColor(c.key, e.target.value.trim())}
                aria-label={`${c.label} colour`}
                maxLength={7}
              />
            </Row>
          ))}
        </Section>
      </div>

      <div className="modal-actions settings-actions">
        <button
          type="button"
          className="btn ghost"
          title="Put every setting back to how the add-on ships (pins stay)"
          onClick={() => {
            setV(pick(d));
            setLimitText(String(d.cardLimit));
            setProblems({});
          }}
        >
          Restore defaults
        </button>
        <span className="spacer" />
        <button type="button" className="btn" onClick={props.onClose}>
          Cancel
        </button>
        <button type="button" className="btn primary" disabled={!dirty || !limitOk || !colorsOk || saving} onClick={save}>
          Save
        </button>
      </div>
    </Modal>
  );
}

function pick(s: SettingsValues): SettingsValues {
  return {
    cardLimit: s.cardLimit,
    countMode: s.countMode,
    unsuspendOnComplete: s.unsuspendOnComplete,
    resourceRoots: [...s.resourceRoots],
    showOnDeck: s.showOnDeck,
    colorSync: s.colorSync,
    colors: { ...s.colors },
    shortcut: s.shortcut,
  };
}

const cleanRoots = (roots: string[]) => roots.map((r) => r.trim()).filter(Boolean);

function Section(props: { title: string; children: ReactNode }) {
  return (
    <section className="set-section">
      <h3>{props.title}</h3>
      <div className="set-card">{props.children}</div>
    </section>
  );
}

/** A setting with its control on the right. */
function Row(props: { label: string; hint?: string; problem?: string; children: ReactNode }) {
  return (
    <div className="set-row">
      <div className="set-text">
        <div className="set-label">{props.label}</div>
        {props.hint && <div className="set-hint">{props.hint}</div>}
        {props.problem && <div className="set-problem">{props.problem}</div>}
      </div>
      <div className="set-control">{props.children}</div>
    </div>
  );
}

/** A setting whose control needs the full width, below its label. */
function Block(props: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="set-row set-block">
      <div className="set-text">
        <div className="set-label">{props.label}</div>
        {props.hint && <div className="set-hint">{props.hint}</div>}
        {props.children}
      </div>
    </div>
  );
}

// --- shortcut ------------------------------------------------------------------

const IS_MAC = /Mac/i.test(navigator.platform);

/** Qt's names for the modifiers, from a key event. On a Mac Qt's "Ctrl"
 *  is ⌘ and "Meta" is ⌃. */
function comboFrom(e: KeyboardEvent): string | null {
  let key: string | null = null;
  const c = e.code;
  if (/^Key[A-Z]$/.test(c)) key = c.slice(3);
  else if (/^Digit\d$/.test(c)) key = c.slice(5);
  else if (/^F\d{1,2}$/.test(c)) key = c;
  else if (c === "Space") key = "Space";
  if (!key) return null;
  const mods = [
    (IS_MAC ? e.metaKey : e.ctrlKey) && "Ctrl",
    (IS_MAC ? e.ctrlKey : e.metaKey) && "Meta",
    e.altKey && "Alt",
    e.shiftKey && "Shift",
  ].filter(Boolean);
  // Plain letters would fire while typing; F-keys may stand alone.
  if (!mods.length && !key.startsWith("F")) return null;
  return [...mods, key].join("+");
}

function displayShortcut(s: string): string {
  if (!IS_MAC) return s.replace(/\+/g, " + ");
  const sym: Record<string, string> = { Ctrl: "⌘", Meta: "⌃", Alt: "⌥", Shift: "⇧" };
  const parts = s.split("+");
  const key = parts.pop() ?? "";
  const order = ["Meta", "Alt", "Shift", "Ctrl"]; // ⌃⌥⇧⌘, the Mac order
  return order.filter((m) => parts.includes(m)).map((m) => sym[m]).join("") + key;
}

function ShortcutField(props: { value: string; onChange: (s: string) => void }) {
  const [recording, setRecording] = useState(false);
  return (
    <div className="shortcut-field">
      <button
        type="button"
        className={`keycap-btn${recording ? " recording" : ""}`}
        onClick={() => setRecording(true)}
        onBlur={() => setRecording(false)}
        onKeyDown={(e) => {
          if (!recording) return;
          e.preventDefault();
          e.stopPropagation(); // Escape cancels recording, not the dialog
          if (e.key === "Escape") return setRecording(false);
          if (e.key === "Backspace" || e.key === "Delete") {
            props.onChange("");
            return setRecording(false);
          }
          const combo = comboFrom(e);
          if (combo) {
            props.onChange(combo);
            setRecording(false);
          }
        }}
        title="Click, then press the keys"
      >
        {recording ? "Press keys…" : props.value ? displayShortcut(props.value) : "None"}
      </button>
      {props.value && !recording && (
        <IconButton size="sm" label="No shortcut" onClick={() => props.onChange("")}>
          <X size={14} />
        </IconButton>
      )}
    </div>
  );
}
