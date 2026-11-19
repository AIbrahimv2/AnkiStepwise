// Logos for the third-party resources AnKing's decks tag cards with
// (Bootcamp, Sketchy, UWorld, ...), so a resource reads at a glance in
// Stepwise and Skim. Each is the brand's own icon: an SVG cut down to its
// symbol where its site had one (OnlineMedEd's is the cat-head "M" of its
// wordmark), otherwise its tab icon at 64px. Where the brand has no symbol
// of its own, only a wordmark, it's a monogram in its colours: B&B's "BB"
// in white on its blue (#0078bc), as its old app icon had it (the B's drawn
// from stems and round bowls), First Aid's "FA" in white on First Aid Team's red
// (#cc2430), the letters from McGraw Hill's vector wordmark, and Pathoma's
// "P" in its red (Helvetica Neue Medium). Divine Intervention's and Dirty
// Medicine's are their podcast cover and YouTube picture, and Physeo's is
// drawn from its 400px icon (circles exact, arrow traced).
// AnKing's own folders (^Systems, Subjects, ...) get AnKing's icon, and
// textbooks a book (Lucide's book-open, ISC).
//
// Logos in colour show as they are; the ones that are all one dark colour
// (Bootcamp, Sketchy, TrueLearn, Physeo, the book) are drawn in
// the text's colour instead, so they show on dark backgrounds too
// (.kit-res-mono in controls.css). The names and logos belong to their
// owners; the add-ons aren't affiliated with them.
//
// Bundled into the page (`?inline`), so Anki serves nothing extra. A name
// with no icon here gets none, and shows its name alone.

import type { CSSProperties } from "react";
import amboss from "./resources/amboss.svg?inline";
import anking from "./resources/anking.png?inline";
import boardsbeyond from "./resources/boardsbeyond.svg?inline";
import book from "./resources/book.svg?inline";
import bootcamp from "./resources/bootcamp.svg?inline";
import dirtymedicine from "./resources/dirtymedicine.png?inline";
import divineintervention from "./resources/divineintervention.png?inline";
import firstaid from "./resources/firstaid.svg?inline";
import nbme from "./resources/nbme.png?inline";
import ninjanerd from "./resources/ninjanerd.svg?inline";
import onlinemeded from "./resources/onlinemeded.svg?inline";
import osmosis from "./resources/osmosis.png?inline";
import pathoma from "./resources/pathoma.svg?inline";
import physeo from "./resources/physeo.svg?inline";
import pixorize from "./resources/pixorize.svg?inline";
import sketchy from "./resources/sketchy.svg?inline";
import truelearn from "./resources/truelearn.png?inline";
import usmlerx from "./resources/usmlerx.png?inline";
import uworld from "./resources/uworld.svg?inline";

/** The logos drawn in the text's colour (see above). */
const MONO = new Set([bootcamp, sketchy, truelearn, physeo, book]);

/** By the name AnKing tags them with (see key). Sketchy's many decks
 *  (SketchyPharm, SketchyIM, ...) share one, in resourceIcon. */
const ICONS: Record<string, string> = {
  amboss,
  "b&b": boardsbeyond,
  bootcamp,
  nbme,
  cms: nbme, // NBME's Clinical Mastery Series
  dirtymedicine,
  divineintervention,
  firstaid,
  ninjanerd,
  ome: onlinemeded,
  omebanner: onlinemeded,
  osmosis,
  pathoma,
  physeo,
  pixorize,
  truelearn,
  combank: truelearn, // TrueLearn's COMBANK
  usmlerx,
  uworld,
  // Books, not brands: a book.
  textbooks: book,
  costanzo: book,
  // AnKing's own folders in its decks, and its other tags.
  systems: anking,
  subjects: anking,
  resourcesbyrotation: anking,
  originaldecks: anking,
  shelf: anking,
  flagthesecards: anking,
  "low/highyield": anking,
  akother: anking,
};

/** A resource's name, however an add-on writes it ("#SketchyPharm",
 *  "OME banner", "Bootcamp (Step 1)"), as ICONS has it. */
function key(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s*\([^)]*\)\s*$/, "")
    .replace(/^[#^!]+/, "")
    .replace(/[\s_]+/g, "");
}

/** The icon for a resource, as a data: URL, or null when it has none. */
export function resourceIcon(name: string): string | null {
  const k = key(name);
  if (ICONS[k]) return ICONS[k];
  if (k.startsWith("sketchy")) return sketchy;
  // AnKing's decks and their other tags ("AK Step1 v12", "AK Original Decks").
  if (/^ak(step|original)/.test(k)) return anking;
  return null;
}

/** The icon for plain-DOM pages (an <img>, or a <span> drawn in the text's
 *  colour), or null. Decorative: the resource's name is beside it. With
 *  `keepRoom`, a resource with no icon gets an empty space its size, so
 *  names in a list still line up. */
export function resourceImg(name: string, keepRoom?: false): HTMLElement | null;
export function resourceImg(name: string, keepRoom: true): HTMLElement;
export function resourceImg(name: string, keepRoom = false): HTMLElement | null {
  const src = resourceIcon(name);
  if (!src) {
    if (!keepRoom) return null;
    const gap = document.createElement("span");
    gap.className = "kit-res-gap";
    return gap;
  }
  if (MONO.has(src)) {
    const mono = document.createElement("span");
    mono.className = "kit-res kit-res-mono";
    mono.style.setProperty("--kit-res-src", `url("${src}")`);
    return mono;
  }
  const img = document.createElement("img");
  img.className = "kit-res";
  img.src = src;
  img.alt = "";
  img.draggable = false;
  return img;
}

/** The icon for React pages; nothing when the resource has none, or with
 *  `keepRoom` an empty space its size, so names in a list line up. */
export function ResourceIcon(props: { name: string; keepRoom?: boolean }) {
  const src = resourceIcon(props.name);
  if (src && MONO.has(src))
    return <span className="kit-res kit-res-mono" style={{ "--kit-res-src": `url("${src}")` } as CSSProperties} />;
  if (src) return <img className="kit-res" src={src} alt="" draggable={false} />;
  return props.keepRoom ? <span className="kit-res-gap" aria-hidden="true" /> : null;
}
