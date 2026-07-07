export const CATEGORIES = [
  "reaction",
  "advice-animal",
  "surreal",
  "political",
  "wholesome",
  "dark",
  "meta",
  "other",
] as const;

export type Category = (typeof CATEGORIES)[number];
