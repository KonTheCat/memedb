import { describe, expect, it } from "vitest";
import type { MemeResponse, SearchResultItem } from "./api";
import { fromMemeResponse, fromSearchResult } from "./display";

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
  it("maps the fields the UI needs off a search result, including similarity", () => {
    const item: SearchResultItem = {
      id: "meme-2",
      blobUrl: "https://example.com/meme-2.png",
      caption: "a cat judging you",
      templateName: "judging-cat",
      tags: ["cat", "judgy"],
      category: "reaction",
      uploadedAt: "2026-01-02T00:00:00Z",
      similarity: 0.87,
    };

    expect(fromSearchResult(item)).toEqual({
      id: "meme-2",
      templateName: "judging-cat",
      tags: ["cat", "judgy"],
      category: "reaction",
      caption: "a cat judging you",
      similarity: 0.87,
    });
  });
});
