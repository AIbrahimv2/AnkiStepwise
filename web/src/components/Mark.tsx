/** The Stepwise mark: three steps with a dot on the middle one, for working
 *  through a deck one topic at a time. Drawn in the current text colour, on the same
 *  24px grid and stroke as the lucide icons around it. The same drawing is
 *  in src/icons/stepwise.svg (the window icon) and src/widget.py (the
 *  deck-screen meter); keep them in step. */
export function Mark({ size = 20, weight = 2.2 }: { size?: number; weight?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={weight}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 18h6v-6h6V6h6" />
      <circle cx="11.3" cy="8.3" r="2" fill="currentColor" stroke="none" />
    </svg>
  );
}
