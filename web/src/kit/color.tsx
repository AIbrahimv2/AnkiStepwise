// A colour setting, shared by AIbrahimv2's Anki add-ons: a chip that opens a
// picker, beside a box to type any CSS colour. The picker has a square for
// how vivid and how bright, a hue slider, an opacity slider when the colour
// may be see-through (`alpha`), and the add-on's own swatches if it has any.
//
// Drawn here, never <input type="color">: the native picker opens a macOS
// panel from the web view, which crashes Anki. Styled by controls.css
// (.color-*). The picker is drawn over everything (above dialogs), and
// Escape closes only it.
//
// Don't edit a vendored copy (web/src/kit/ in an add-on): change it in the
// kit and run its sync.py.

import {
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type Ref,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { useEscape } from "./controls";

/** Red, green and blue 0-255, alpha 0-1. */
export interface Rgba {
  r: number;
  g: number;
  b: number;
  a: number;
}

/** Hue 0-360; saturation, value and alpha 0-1. */
interface Hsva {
  h: number;
  s: number;
  v: number;
  a: number;
}

const CHECKER = "repeating-conic-gradient(#d6d6d6 0 25%, #ffffff 0 50%)";
let probe: CanvasRenderingContext2D | null | undefined;

/** Any CSS colour ("#f90", "rgba(0,0,0,0.4)", "transparent", "teal"...) as
 *  RGBA, or null if it isn't one. The browser reads it, through a canvas. */
export function parseColor(text: string): Rgba | null {
  const s = text.trim();
  if (!s) return null;
  if (probe === undefined) probe = document.createElement("canvas").getContext("2d");
  if (!probe) return null;
  // A canvas keeps its old colour when it can't read the new one, so read it
  // over two different ones: a real colour comes out the same both times.
  probe.fillStyle = "#000000";
  probe.fillStyle = s;
  const one = String(probe.fillStyle);
  probe.fillStyle = "#ffffff";
  probe.fillStyle = s;
  if (String(probe.fillStyle) !== one) return null;
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(one);
  if (hex) return { r: parseInt(hex[1], 16), g: parseInt(hex[2], 16), b: parseInt(hex[3], 16), a: 1 };
  const fn = /^rgba?\(([^)]*)\)$/i.exec(one);
  if (!fn) return null;
  const [r, g, b, a = 1] = fn[1].split(",").map(Number);
  return [r, g, b, a].every(Number.isFinite) ? { r, g, b, a } : null;
}

/** "#rrggbb", or "rgba(r,g,b,a)" where the colour may be see-through. */
export function formatColor(c: Rgba, alpha: boolean): string {
  const [r, g, b] = [c.r, c.g, c.b].map((n) => Math.max(0, Math.min(255, Math.round(n))));
  if (alpha) return `rgba(${r},${g},${b},${+Math.max(0, Math.min(1, c.a)).toFixed(2)})`;
  return `#${[r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("")}`;
}

function toHsva({ r, g, b, a }: Rgba): Hsva {
  const [R, G, B] = [r / 255, g / 255, b / 255];
  const max = Math.max(R, G, B);
  const d = max - Math.min(R, G, B);
  let h = 0;
  if (d) {
    if (max === R) h = ((G - B) / d) % 6;
    else if (max === G) h = (B - R) / d + 2;
    else h = (R - G) / d + 4;
    h = (h * 60 + 360) % 360;
  }
  return { h, s: max ? d / max : 0, v: max, a };
}

function toRgba({ h, s, v, a }: Hsva): Rgba {
  const f = (n: number) => {
    const k = (n + h / 60) % 6;
    return (v - v * s * Math.max(0, Math.min(k, 4 - k, 1))) * 255;
  };
  return { r: f(5), g: f(3), b: f(1), a };
}

const clamp01 = (n: number) => Math.max(0, Math.min(1, n));

export function ColorField(props: {
  value: string;
  onChange: (value: string) => void;
  /** What the colour is for, for screen readers ("Queued", "In dark mode"). */
  label: string;
  /** May it be see-through? Then it's written as rgba(), else as #rrggbb. */
  alpha?: boolean;
  /** Colours to offer at the bottom of the picker. */
  swatches?: string[];
  /** Mark it as wrong (the add-on found a problem with it). */
  bad?: boolean;
}) {
  const { value, onChange, label } = props;
  const alpha = !!props.alpha;
  const field = useRef<HTMLDivElement>(null);
  const chip = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const parsed = parseColor(value);
  const bad = props.bad || (!!value.trim() && !parsed);
  const fill = parsed ? formatColor(parsed, true) : "transparent";

  return (
    <div ref={field} className="color-field">
      <button
        ref={chip}
        type="button"
        className={`color-chip${open ? " open" : ""}`}
        aria-label={`Pick a colour for ${label}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ backgroundImage: `linear-gradient(${fill}, ${fill}), ${CHECKER}`, backgroundSize: "auto, 8px 8px" }} />
      </button>
      <input
        className={`set-input mono color-text${alpha ? " wide" : ""}${bad ? " bad" : ""}`}
        value={value}
        spellCheck={false}
        aria-label={label}
        aria-invalid={bad}
        onChange={(e) => onChange(e.target.value)}
        // Tidy what was typed ("#F90" → "#ff9900") once it's a colour.
        onBlur={() => {
          if (!parsed) return;
          const tidy = formatColor(parsed, alpha);
          if (tidy !== value) onChange(tidy);
        }}
      />
      {open && chip.current && field.current && (
        <ColorPicker
          anchor={chip.current}
          field={field.current}
          value={value}
          alpha={alpha}
          swatches={props.swatches}
          label={label}
          onChange={onChange}
          onClose={close}
        />
      )}
    </div>
  );
}

function ColorPicker(props: {
  /** The chip it opens under, and the whole field (chip and box), whose
   *  clicks leave it open: what's typed in the box shows in it. */
  anchor: HTMLElement;
  field: HTMLElement;
  value: string;
  alpha: boolean;
  swatches?: string[];
  label: string;
  onChange: (value: string) => void;
  onClose: () => void;
}) {
  const { anchor, field, alpha, onClose } = props;
  const ref = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLDivElement>(null);
  // Hue, vividness and brightness are kept here rather than read back from
  // the value, so the hue holds while the colour is grey, white or black.
  const [hsva, setHsva] = useState<Hsva>(() => toHsva(parseColor(props.value) ?? { r: 0, g: 0, b: 0, a: 1 }));
  const sent = useRef<string | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  // Follow what's typed in the box while the picker is open.
  useEffect(() => {
    if (props.value === sent.current) return;
    const c = parseColor(props.value);
    if (c) setHsva(toHsva(c));
  }, [props.value]);

  const pick = (next: Hsva) => {
    const c = { ...next, a: alpha ? next.a : 1 };
    setHsva(c);
    const out = formatColor(toRgba(c), alpha);
    sent.current = out;
    props.onChange(out);
  };

  // Under the chip, or over it when there's no room below; inside the window.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = anchor.getBoundingClientRect();
    const { width, height } = el.getBoundingClientRect();
    const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8));
    let top = r.bottom + 6;
    if (top + height > window.innerHeight - 8) top = Math.max(8, r.top - height - 6);
    setPos({ left, top });
  }, [anchor]);

  // Focus the square once the picker is placed (hidden, it can't take the
  // focus), ready for the arrow keys...
  const placed = pos !== null;
  useLayoutEffect(() => {
    if (placed) area.current?.focus({ preventScroll: true });
  }, [placed]);
  // ...and give it back to the chip after: a layout effect, so it runs while
  // the picker still holds it.
  useLayoutEffect(() => {
    const el = ref.current;
    return () => {
      if (el?.contains(document.activeElement)) anchor.focus({ preventScroll: true });
    };
  }, [anchor]);

  useEscape(onClose);
  useEffect(() => {
    const outside = (e: Event) => {
      const t = e.target as Node | null;
      if (t && (ref.current?.contains(t) || field.contains(t))) return;
      onClose();
    };
    window.addEventListener("mousedown", outside, true);
    window.addEventListener("scroll", outside, true);
    window.addEventListener("blur", onClose);
    window.addEventListener("resize", onClose);
    return () => {
      window.removeEventListener("mousedown", outside, true);
      window.removeEventListener("scroll", outside, true);
      window.removeEventListener("blur", onClose);
      window.removeEventListener("resize", onClose);
    };
  }, [field, onClose]);

  const solid = formatColor(toRgba({ ...hsva, a: 1 }), false);
  const current = formatColor(toRgba(hsva), alpha);
  const percent = (n: number) => `${Math.round(n * 100)}%`;

  return createPortal(
    <div
      ref={ref}
      className="color-pop"
      role="dialog"
      aria-label={`Colour for ${props.label}`}
      style={pos ?? { visibility: "hidden" }}
    >
      <Area
        ref={area}
        hue={hsva.h}
        s={hsva.s}
        v={hsva.v}
        thumb={solid}
        onChange={(s, v) => pick({ ...hsva, s, v })}
      />
      <Track
        className="color-hue"
        label="Hue"
        value={hsva.h / 360}
        text={`${Math.round(hsva.h)}°`}
        thumb={`hsl(${hsva.h} 100% 50%)`}
        onChange={(x) => pick({ ...hsva, h: Math.min(x * 360, 359.9) })}
      />
      {alpha && (
        <Track
          label="Opacity"
          value={hsva.a}
          text={percent(hsva.a)}
          thumb={solid}
          style={{
            backgroundImage: `linear-gradient(to right, transparent, ${solid}), ${CHECKER}`,
            backgroundSize: "auto, 8px 8px",
          }}
          onChange={(a) => pick({ ...hsva, a })}
        />
      )}
      {!!props.swatches?.length && (
        <div className="swatches color-swatches">
          {props.swatches.map((s) => {
            const c = parseColor(s);
            if (!c) return null;
            const on = formatColor(c, alpha) === current;
            return (
              <button
                key={s}
                type="button"
                className={`swatch-btn${on ? " on" : ""}`}
                style={{ backgroundImage: `linear-gradient(${s}, ${s}), ${CHECKER}`, backgroundSize: "auto, 8px 8px" }}
                aria-label={s}
                aria-pressed={on}
                title={s}
                onClick={() => pick(toHsva(c))}
              />
            );
          })}
        </div>
      )}
    </div>,
    document.getElementById("root") ?? document.body,
  );
}

/** Steps for the arrow keys: 1%, or 10% with Shift. */
function step(e: ReactKeyboardEvent) {
  return e.shiftKey ? 0.1 : 0.01;
}

/** Drags that keep going outside the element, as long as the button's down. */
function drag(e: ReactPointerEvent<HTMLElement>, at: (x: number, y: number) => void) {
  const el = e.currentTarget;
  const go = (ev: { clientX: number; clientY: number }) => {
    const r = el.getBoundingClientRect();
    at(clamp01((ev.clientX - r.left) / r.width), clamp01((ev.clientY - r.top) / r.height));
  };
  if (e.type === "pointerdown") {
    el.setPointerCapture(e.pointerId);
    el.focus({ preventScroll: true });
    e.preventDefault();
    go(e);
  } else if (el.hasPointerCapture(e.pointerId)) go(e);
}

/** The square: vividness left to right, brightness bottom to top. */
function Area(props: {
  ref: Ref<HTMLDivElement>;
  hue: number;
  s: number;
  v: number;
  thumb: string;
  onChange: (s: number, v: number) => void;
}) {
  const { s, v, onChange } = props;
  const move = (e: ReactPointerEvent<HTMLDivElement>) => drag(e, (x, y) => onChange(x, 1 - y));
  return (
    <div
      ref={props.ref}
      className="color-area"
      role="slider"
      tabIndex={0}
      aria-label="Vividness and brightness"
      aria-valuetext={`${Math.round(s * 100)}% vivid, ${Math.round(v * 100)}% bright`}
      style={{ backgroundColor: `hsl(${props.hue} 100% 50%)` }}
      onPointerDown={move}
      onPointerMove={move}
      onKeyDown={(e) => {
        const d = step(e);
        const keys: Record<string, [number, number]> = {
          ArrowLeft: [-d, 0],
          ArrowRight: [d, 0],
          ArrowUp: [0, d],
          ArrowDown: [0, -d],
        };
        const k = keys[e.key];
        if (!k) return;
        e.preventDefault();
        onChange(clamp01(s + k[0]), clamp01(v + k[1]));
      }}
    >
      <span className="color-thumb" style={{ left: `${s * 100}%`, top: `${(1 - v) * 100}%`, background: props.thumb }} />
    </div>
  );
}

/** A slider from 0 to 1 (hue or opacity). */
function Track(props: {
  label: string;
  value: number;
  text: string;
  thumb: string;
  className?: string;
  style?: CSSProperties;
  onChange: (x: number) => void;
}) {
  const { value, onChange } = props;
  const move = (e: ReactPointerEvent<HTMLDivElement>) => drag(e, (x) => onChange(x));
  return (
    <div
      className={`color-track${props.className ? ` ${props.className}` : ""}`}
      role="slider"
      tabIndex={0}
      aria-label={props.label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(value * 100)}
      aria-valuetext={props.text}
      style={props.style}
      onPointerDown={move}
      onPointerMove={move}
      onKeyDown={(e) => {
        const d = step(e);
        const next =
          e.key === "ArrowLeft" || e.key === "ArrowDown"
            ? value - d
            : e.key === "ArrowRight" || e.key === "ArrowUp"
              ? value + d
              : e.key === "Home"
                ? 0
                : e.key === "End"
                  ? 1
                  : null;
        if (next === null) return;
        e.preventDefault();
        onChange(clamp01(next));
      }}
    >
      <span className="color-thumb" style={{ left: `${value * 100}%`, background: props.thumb }} />
    </div>
  );
}
