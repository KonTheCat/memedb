// Shared CSV shape with scripts/calibrate_thresholds.py's labeling template:
// query_id,query,rank,meme_id,caption,templateName,cosine,label
export interface CalibrationRow {
  queryId: string;
  query: string;
  rank: number;
  memeId: string;
  caption: string;
  templateName: string;
  cosine: number;
  label: 0 | 1 | 2;
}

const HEADER = ["query_id", "query", "rank", "meme_id", "caption", "templateName", "cosine", "label"];

function escapeField(value: string): string {
  if (/[",\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export function buildCsv(rows: CalibrationRow[]): string {
  const lines = [HEADER.join(",")];
  for (const row of rows) {
    lines.push(
      [
        row.queryId,
        row.query,
        String(row.rank),
        row.memeId,
        row.caption,
        row.templateName,
        row.cosine.toFixed(4),
        String(row.label),
      ]
        .map(escapeField)
        .join(","),
    );
  }
  return lines.join("\n") + "\n";
}

function parseLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (inQuotes) {
      if (char === '"' && line[i + 1] === '"') {
        current += '"';
        i++;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        current += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      fields.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  fields.push(current);
  return fields;
}

// Splits CSV text into records, respecting quoted fields that contain
// embedded newlines (captions can contain commas, but not newlines today -
// handled anyway since it's cheap and avoids a subtle future bug).
function splitRecords(text: string): string[] {
  const records: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') inQuotes = !inQuotes;
    if (char === "\n" && !inQuotes) {
      records.push(current);
      current = "";
    } else if (char !== "\r") {
      current += char;
    }
  }
  if (current.trim() !== "") records.push(current);
  return records;
}

export function parseCsv(text: string): CalibrationRow[] {
  const records = splitRecords(text.trim());
  if (records.length === 0) return [];

  const [header, ...dataRecords] = records;
  const columns = parseLine(header);
  const indexOf = (name: string) => columns.indexOf(name);

  const idx = {
    queryId: indexOf("query_id"),
    query: indexOf("query"),
    rank: indexOf("rank"),
    memeId: indexOf("meme_id"),
    caption: indexOf("caption"),
    templateName: indexOf("templateName"),
    cosine: indexOf("cosine"),
    label: indexOf("label"),
  };

  const rows: CalibrationRow[] = [];
  for (const record of dataRecords) {
    if (record.trim() === "") continue;
    const fields = parseLine(record);
    const labelText = fields[idx.label]?.trim() ?? "";
    if (labelText === "") continue; // unlabeled rows aren't calibration data yet

    rows.push({
      queryId: fields[idx.queryId] ?? "",
      query: fields[idx.query] ?? "",
      rank: Number(fields[idx.rank] ?? 0),
      memeId: fields[idx.memeId] ?? "",
      caption: fields[idx.caption] ?? "",
      templateName: fields[idx.templateName] ?? "",
      cosine: Number(fields[idx.cosine] ?? 0),
      label: (Number(labelText) as 0 | 1 | 2) ?? 0,
    });
  }
  return rows;
}

// Deterministic so independently exported CSVs merge cleanly instead of
// renumbering query_id per session.
export function slugifyQuery(query: string): string {
  const slug = query
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "query";
}

export function mergeRows(existing: CalibrationRow[], incoming: CalibrationRow[]): CalibrationRow[] {
  const byKey = new Map<string, CalibrationRow>();
  for (const row of existing) byKey.set(`${row.queryId}:${row.memeId}`, row);
  for (const row of incoming) byKey.set(`${row.queryId}:${row.memeId}`, row); // incoming/newest wins
  return Array.from(byKey.values());
}
