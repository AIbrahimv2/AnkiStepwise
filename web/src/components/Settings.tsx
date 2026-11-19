import { Plus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import "../settings.css";
import { call } from "../bridge";
import type { CountMode, PinnedResource, Settings, SettingsValues, StatusColors } from "../types";
import { StepChip } from "./Tree";
import { ColorField } from "../kit/color";
import { Block, Row, Section, SettingsFoot, ShortcutField } from "../kit/settings";
import { IconButton, Switch } from "./ui";

const LIMIT_MIN = 1;
const LIMIT_MAX = 5000;
/** Cmd on a Mac, Ctrl elsewhere, as the size keys are. */
const MOD = typeof navigator !== "undefined" && /Mac/.test(navigator.platform) ? "⌘" : "Ctrl+";

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

// Colorful Tags' palette, offered in the kit's colour picker.
const PALETTE = ["#ff9300", "#00f900", "#af52de", "#ff2600", "#0096ff", "#fefb00", "#ff40ff", "#00fdff", "#929292"];
const HEX = /^#[0-9a-f]{6}$/i;

const COLOR_ROWS: { key: keyof StatusColors; label: string }[] = [
  { key: "queued", label: "Queued" },
  { key: "completed", label: "Done" },
  { key: "later", label: "Later" },
];

/** Settings for the add-on, edited here rather than as JSON in Anki's
 *  config editor (Anki's Config button opens this too). Changes apply on
 *  Save. They're a tab of the add-on kit's window, beside What's new and
 *  About (settings-main.tsx); the Stepwise window hears of a save from
 *  Python ("settingsSaved"). */
export function SettingsPanel(props: { onClose: () => void }) {
  const [loaded, setLoaded] = useState<Settings | null>(null);
  const [v, setV] = useState<SettingsValues | null>(null);
  const [limitText, setLimitText] = useState("");
  const [pinned, setPinned] = useState<PinnedResource[]>([]);
  const [matches, setMatches] = useState<(string[] | null)[]>([]);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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

  if (!loaded || !v) return <div className="skeleton" style={{ height: 320, marginTop: 28, borderRadius: 12 }} />;

  const set = <K extends keyof SettingsValues>(key: K, value: SettingsValues[K]) => {
    setV({ ...v, [key]: value });
    setProblems(({ [key]: _gone, ...rest }) => rest);
    setSaved(false);
  };
  const setColor = (key: keyof StatusColors, value: string) => {
    setV({ ...v, colors: { ...v.colors, [key]: value } });
    setProblems(({ [`colors.${key}`]: _gone, ...rest }) => rest);
    setSaved(false);
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
      const r = await call<{ settings: Settings; problems?: Record<string, string> }>("save_settings", {
        settings: { ...current, pinned: pinned.map((p) => p.tag) },
      });
      if (r.problems) setProblems(r.problems);
      else {
        // What's saved is the new starting point (Python cleaned it up).
        setLoaded(r.settings);
        setV(pick(r.settings));
        setLimitText(String(r.settings.cardLimit));
        setPinned(r.settings.pinned);
        setSaved(true);
      }
    } finally {
      setSaving(false);
    }
  };

  const mode = MODES.find((m) => m.value === v.countMode) ?? MODES[0];
  const d = loaded.defaults;

  return (
    <>
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

        <Section title="Window">
          <Row
            label="Size"
            hint={`How big everything in the window draws. ${MOD}= and ${MOD}− change it in steps as you work; ${MOD}0 puts it back to 100%.`}
            problem={problems.size}
          >
            <span className="pct-field">
              <input
                className={`set-input num${problems.size ? " bad" : ""}`}
                inputMode="numeric"
                value={String(v.size)}
                onChange={(e) => set("size", Number(e.target.value.replace(/\D/g, "")) || 0)}
                aria-label="Percentage"
              />
              %
            </span>
          </Row>
        </Section>

        <Section title="Anki">
          <Row label="Meter on the deck screen" hint="A small queue meter under your deck list. Click it to open Stepwise.">
            <Switch checked={v.showOnDeck} label="" onChange={(x) => set("showOnDeck", x)} />
          </Row>
          <Row label="Shortcut" hint="Opens Stepwise from Anki's main window." problem={problems.shortcut}>
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
              <ColorField
                value={v.colors[c.key]}
                onChange={(x) => setColor(c.key, x.trim())}
                label={c.label}
                swatches={PALETTE}
                bad={!HEX.test(v.colors[c.key]) || !!problems[`colors.${c.key}`]}
              />
            </Row>
          ))}
        </Section>
      </div>
      <SettingsFoot
        onRestore={() => {
          setV(pick(d));
          setLimitText(String(d.cardLimit));
          setProblems({});
          setSaved(false);
        }}
        restoreTitle="Put every setting back to how the add-on ships (pins stay)"
        saved={saved && !dirty}
        onClose={props.onClose}
        onSave={save}
        saveDisabled={!dirty || !limitOk || !colorsOk || saving}
      />
    </>
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
    size: s.size,
  };
}

const cleanRoots = (roots: string[]) => roots.map((r) => r.trim()).filter(Boolean);
