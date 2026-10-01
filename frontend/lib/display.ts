import type { MemeResponse, RelevanceBucket, SearchResultItem } from "./api";

export interface DisplayMeme {
  id: string;
  templateName: string;
  tags: string[];
  category: string;
  ocrText?: string;
  caption?: string;
  bucket?: RelevanceBucket;
  matchedTerms?: string[];
}

export function fromMemeResponse(doc: MemeResponse): DisplayMeme {
  return {
    id: doc.id,
    templateName: doc.templateName,
    tags: doc.tags,
    category: doc.category,
    ocrText: doc.ocrText,
    caption: doc.caption,
  };
}

export function fromSearchResult(item: SearchResultItem): DisplayMeme {
  return {
    id: item.id,
    templateName: item.templateName,
    tags: item.tags,
    category: item.category,
    ocrText: item.ocrText,
    caption: item.caption,
    bucket: item.bucket,
    matchedTerms: item.matchedTerms,
  };
}

export interface TextSegment {
  text: string;
  highlighted: boolean;
}

// Matched terms come from the backend's stemmed token set (see
// memedb/relevance.py), so "cat" means the document had the literal token
// "cat" - it must not light up inside unrelated words like "category". Only
// extend the match over the same suffixes the backend stemmer strips, so a
// plural/inflected form in the displayed text (e.g. "cats", "dogging") still
// highlights, without swallowing an unrelated longer word that merely starts
// with the same letters.
const STEM_SUFFIXES = ["'s", "ing", "ed", "es", "s"];

export function highlightSegments(text: string, matchedTerms: string[]): TextSegment[] {
  const terms = matchedTerms.filter(Boolean);
  if (!text || terms.length === 0) return [{ text, highlighted: false }];

  const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const suffixes = STEM_SUFFIXES.join("|");
  const pattern = new RegExp(`\\b(?:${escaped.join("|")})(?:${suffixes})?\\b`, "gi");

  const segments: TextSegment[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > lastIndex) segments.push({ text: text.slice(lastIndex, start), highlighted: false });
    segments.push({ text: match[0], highlighted: true });
    lastIndex = start + match[0].length;
  }
  if (lastIndex < text.length) segments.push({ text: text.slice(lastIndex), highlighted: false });
  return segments;
}

function stem(token: string): string {
  for (const suffix of STEM_SUFFIXES) {
    if (token.length > suffix.length + 2 && token.endsWith(suffix)) {
      return token.slice(0, -suffix.length);
    }
  }
  return token;
}

// Same false-positive hazard as highlightSegments: a naive startsWith("cat")
// would match the tag "category". Stem the tag's own words the same way the
// backend stems document tokens, and compare whole stems, not prefixes.
export function isTagMatched(tag: string, matchedTerms: string[]): boolean {
  const terms = new Set(matchedTerms);
  const words = tag.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  return words.some((word) => terms.has(stem(word)));
}

const BUCKET_LABELS: Record<string, string> = {
  strong: "Strong match",
  possible: "Possible match",
  weak: "Weak match",
  near_duplicate: "Near duplicate",
  similar: "Similar",
  loose: "Loose match",
};

export function bucketLabel(bucket: string): string {
  return BUCKET_LABELS[bucket] ?? bucket;
}
