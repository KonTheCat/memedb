import { describe, expect, it } from "vitest";
import type { MemeResponse, SearchResultItem } from "./api";
import { bucketLabel, fromMemeResponse, fromSearchResult, highlightSegments, isTagMatched } from "./display";

describe("fromMemeResponse", () => {
  it("maps the fields the UI needs off a full meme document", () => {
    const doc: MemeResponse = {
      id: "meme-1",
      category: "reaction",
      blobUrl: "https://example.com/meme-1.png",
      fileHash: "abc123",
      uploadedAt: "2026-01-01T00:00:00Z",
      originalFilename: "doge.png",
      ocrText: "such wow",
      caption: "a dog looking skeptical",
      templateName: "doge",
      tags: ["dog", "meme"],
      sourceUrl: "https://example.com/src",
      searchableText: "such wow a dog looking skeptical doge dog meme",
      embeddingModel: "fake-vision-v1",
      embeddingDimensions: 1024,
      viewCount: 0,
    };

    expect(fromMemeResponse(doc)).toEqual({
      id: "meme-1",
      templateName: "doge",
      tags: ["dog", "meme"],
      category: "reaction",
      ocrText: "such wow",
      caption: "a dog looking skeptical",
    });
  });
});

describe("fromSearchResult", () => {
  it("maps the fields the UI needs off a search result, including bucket and matched terms", () => {
    const item: SearchResultItem = {
      id: "meme-2",
      blobUrl: "https://example.com/meme-2.png",
      ocrText: "much judge",
      caption: "a cat judging you",
      templateName: "judging-cat",
      tags: ["cat", "judgy"],
      category: "reaction",
      uploadedAt: "2026-01-02T00:00:00Z",
      similarity: 0.87,
      bucket: "strong",
      matchedTerms: ["cat"],
    };

    expect(fromSearchResult(item)).toEqual({
      id: "meme-2",
      templateName: "judging-cat",
      tags: ["cat", "judgy"],
      category: "reaction",
      ocrText: "much judge",
      caption: "a cat judging you",
      bucket: "strong",
      matchedTerms: ["cat"],
    });
  });
});

describe("highlightSegments", () => {
  it("highlights whole-word matches, not substrings", () => {
    const segments = highlightSegments("a category of cats", ["cat"]);
    expect(segments).toEqual([
      { text: "a category of ", highlighted: false },
      { text: "cats", highlighted: true },
    ]);
  });

  it("returns the text unhighlighted when there are no matched terms", () => {
    expect(highlightSegments("hello world", [])).toEqual([{ text: "hello world", highlighted: false }]);
  });
});

describe("isTagMatched", () => {
  it("matches a tag against a stemmed term", () => {
    expect(isTagMatched("dogs", ["dog"])).toBe(true);
    expect(isTagMatched("category", ["cat"])).toBe(false);
  });
});

describe("bucketLabel", () => {
  it("maps known buckets to display labels", () => {
    expect(bucketLabel("strong")).toBe("Strong match");
    expect(bucketLabel("near_duplicate")).toBe("Near duplicate");
  });
});
