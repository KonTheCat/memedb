import { describe, expect, it } from "vitest";
import { buildCsv, mergeRows, parseCsv, slugifyQuery, type CalibrationRow } from "./calibrationCsv";

const ROW: CalibrationRow = {
  queryId: "dog",
  query: "dog",
  rank: 1,
  memeId: "meme-1",
  caption: "a dog looking skeptical",
  templateName: "doge",
  cosine: 0.9123,
  label: 2,
};

describe("buildCsv / parseCsv round trip", () => {
  it("round-trips a simple row", () => {
    const csv = buildCsv([ROW]);
    expect(parseCsv(csv)).toEqual([ROW]);
  });

  it("round-trips a caption containing a comma", () => {
    const row: CalibrationRow = { ...ROW, caption: "such wow, very meme" };
    const csv = buildCsv([row]);
    expect(csv).toContain('"such wow, very meme"');
    expect(parseCsv(csv)).toEqual([row]);
  });

  it("round-trips a caption containing a quote", () => {
    const row: CalibrationRow = { ...ROW, caption: 'he said "hello"' };
    const csv = buildCsv([row]);
    expect(parseCsv(csv)).toEqual([row]);
  });

  it("skips rows with no label", () => {
    const csv =
      "query_id,query,rank,meme_id,caption,templateName,cosine,label\n" + "dog,dog,1,meme-1,caption,doge,0.9,\n";
    expect(parseCsv(csv)).toEqual([]);
  });

  it("returns an empty array for an empty export", () => {
    expect(parseCsv(buildCsv([]))).toEqual([]);
  });
});

describe("slugifyQuery", () => {
  it("lowercases and hyphenates", () => {
    expect(slugifyQuery("Drake Pointing")).toBe("drake-pointing");
  });

  it("strips punctuation", () => {
    expect(slugifyQuery("when the code finally works!")).toBe("when-the-code-finally-works");
  });

  it("falls back to a non-empty slug", () => {
    expect(slugifyQuery("???")).toBe("query");
  });
});

describe("mergeRows", () => {
  it("keeps rows unique by (queryId, memeId), newest wins", () => {
    const older: CalibrationRow = { ...ROW, label: 1 };
    const newer: CalibrationRow = { ...ROW, label: 2 };
    expect(mergeRows([older], [newer])).toEqual([newer]);
  });

  it("concatenates distinct rows", () => {
    const other: CalibrationRow = { ...ROW, memeId: "meme-2" };
    const merged = mergeRows([ROW], [other]);
    expect(merged).toHaveLength(2);
  });
});
