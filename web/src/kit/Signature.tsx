// AIbrahimv2's signature, the sign-off at the end of About. Drawn from
// assets/signature.svg (the strokes follow the text colour; the underline
// keeps its red). Inline, so no add-on has to serve a file for it.
//
// It writes itself on, as in the Ownus app: when it comes into view the
// strokes are inked one after another, left to right, then the red
// underline. The pen moves at one steady speed, so each stroke takes its
// share of DRAW_MS by length. It all runs here (Web Animations), so it needs
// no stylesheet. With reduced motion, or where the browser can't watch or
// animate, the finished signature is simply there.
//
// Don't edit a vendored copy (web/src/kit/ in an add-on): change it in the
// kit and run its sync.py.

import { useEffect, useRef, useState } from "react";

const STROKES = [
  "M12 88 C 22 48, 37 24, 51 24 C 65 24, 66 54, 70 88",
  "M32 66 C 52 58, 72 60, 86 62",
  "M86 62 C 80 58, 86 22, 93 23 C 99 24, 96 60, 92 80 C 100 70, 113 70, 114 80 C 115 89, 104 88, 99 80 C 106 82, 114 80, 122 78",
  "M134 60 C 127 57, 119 70, 126 79 C 132 85, 140 80, 139 72 C 139 44, 145 23, 150 24 C 155 25, 151 58, 151 80 C 156 81, 160 79, 165 77",
  "M164 79 C 168 70, 172 63, 176 64 C 181 65, 180 72, 173 72 C 168 72, 167 76, 171 79 C 175 81, 182 78, 188 73",
  "M188 73 C 186 42, 195 21, 201 23 C 206 25, 200 60, 200 81",
  "M214 84 C 214 56, 222 30, 230 32 C 237 34, 224 60, 222 82 C 230 64, 244 60, 246 78 C 247 86, 240 86, 240 78 C 242 64, 252 62, 256 76",
  "M256 76 C 258 64, 268 60, 271 74 C 273 84, 266 84, 266 76 C 268 62, 278 62, 282 78 C 290 64, 300 64, 300 80 C 308 64, 320 64, 322 80 C 324 86, 332 84, 334 76 C 338 62, 350 64, 354 80",
];
const UNDERLINE = "M20 94 C 130 102, 280 92, 350 60";

// The pen's time across the whole signature, underline included.
const DRAW_MS = 1200;
// A beat once the signature is in view, before the pen touches down.
const BEAT_MS = 250;

// Until a stroke's turn it is dashed away (pathLength 1 makes one dash the
// whole stroke) and transparent: a round cap still paints a dot at the start
// of a fully dashed-away stroke.
const UNINKED = { strokeDasharray: "1", strokeDashoffset: "1", opacity: "0" };

type Ink = "waiting" | "writing" | "done";

function canWrite(): boolean {
  return (
    typeof IntersectionObserver === "function" &&
    typeof Element.prototype.animate === "function" &&
    !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

export function Signature(props: { label: string; className?: string }) {
  const svg = useRef<SVGSVGElement>(null);
  const [ink, setInk] = useState<Ink>(() => (canWrite() ? "waiting" : "done"));

  // Start writing once most of it is in view (About may open scrolled above it).
  useEffect(() => {
    const el = svg.current;
    if (ink !== "waiting" || !el) return;
    const seen = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        seen.disconnect();
        setInk("writing");
      },
      { threshold: 0.6 },
    );
    seen.observe(el);
    return () => seen.disconnect();
  }, [ink]);

  useEffect(() => {
    const el = svg.current;
    if (ink !== "writing" || !el) return;
    const paths = Array.from(el.querySelectorAll("path"));
    const lengths = paths.map((p) => p.getTotalLength());
    const total = lengths.reduce((sum, n) => sum + n, 0) || 1;
    let at = BEAT_MS;
    const strokes = paths.map((p, i) => {
      const duration = (lengths[i] / total) * DRAW_MS;
      const stroke = p.animate(
        [
          { opacity: 1, strokeDashoffset: 1 },
          { opacity: 1, strokeDashoffset: 0 },
        ],
        { duration, delay: at, easing: "linear", fill: "forwards" },
      );
      at += duration;
      return stroke;
    });
    strokes[strokes.length - 1].finished.then(
      () => setInk("done"),
      () => undefined, // cancelled: About closed or the tab changed mid-stroke
    );
    return () => strokes.forEach((s) => s.cancel());
  }, [ink]);

  const style = ink === "done" ? undefined : UNINKED;
  return (
    <svg ref={svg} className={props.className} viewBox="0 0 330 110" fill="none" role="img" aria-label={props.label}>
      <g transform="scale(0.85,1)" strokeLinecap="round" strokeLinejoin="round">
        {STROKES.map((d) => (
          <path key={d} d={d} stroke="currentColor" strokeWidth={3.1} pathLength={1} style={style} />
        ))}
        <path d={UNDERLINE} stroke="#ff2400" strokeWidth={3} pathLength={1} style={style} />
      </g>
    </svg>
  );
}
