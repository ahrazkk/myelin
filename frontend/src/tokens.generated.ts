// Generated from styles.css by `python -m myelin_design export`. Do not edit by hand.
// CI fails if this file does not match the stylesheet.

/** The accent colour for each accent setting, by day and by night. */
export const ACCENT_COLORS = {
  myelin: { day: "#2d6bad", night: "#57c4e5" },
  emerald: { day: "#1f7a5a", night: "#4fd1a1" },
  amber: { day: "#9a5b12", night: "#f2b25c" },
  rose: { day: "#b03a6a", night: "#f28bb0" },
} as const;

/** Day values of the opaque tokens as [red, green, blue], for canvas code. */
export const DAY_RGB = {
  slide: [237, 239, 245],
  ink: [27, 33, 66],
  muted: [93, 100, 133],
  hair: [204, 209, 224],
  "axon-ahead": [194, 200, 218],
  myelin: [45, 107, 173],
  cresyl: [123, 63, 158],
} as const satisfies Record<string, readonly [number, number, number]>;
