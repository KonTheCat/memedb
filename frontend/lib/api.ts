import { getAccessToken } from "./auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface MemeResponse {
  id: string;
  category: string;
  blobUrl: string;
  fileHash: string;
  uploadedAt: string;
  originalFilename: string;
  ocrText: string;
  caption: string;
  templateName: string;
  tags: string[];
  sourceUrl: string;
  searchableText: string;
  embeddingModel: string;
  embeddingDimensions: number;
  viewCount: number;
}

export interface SearchResultItem {
  id: string;
  blobUrl: string;
  caption: string;
  templateName: string;
  tags: string[];
  category: string;
  uploadedAt: string;
  similarity: number;
}

export interface IngestResponse {
  id: string;
  blobUrl: string;
}

export interface UpdateMemePayload {
  category?: string;
  templateName?: string;
  caption?: string;
  ocrText?: string;
  tags?: string[];
  sourceUrl?: string;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    // 401 means no/expired token - send the user to sign in. 403 means they're
    // signed in but lack the Admin role, which signing in again won't fix, so
    // just surface the error instead.
    if (res.status === 401 && typeof window !== "undefined") {
      window.location.href = "/login";
    }
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {
      // response body wasn't JSON — fall back to statusText already set above
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

export function imageUrl(id: string): string {
  return `${API_BASE_URL}/memes/${id}/image`;
}

// Public - browse/search/read, no auth header sent.

export function listMemes(category: string | null, limit = 24, offset = 0): Promise<MemeResponse[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (category) params.set("category", category);
  return fetch(`${API_BASE_URL}/memes?${params}`).then((res) => handle<MemeResponse[]>(res));
}

export function countMemes(category: string | null): Promise<number> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  return fetch(`${API_BASE_URL}/memes/count?${params}`)
    .then((res) => handle<{ count: number }>(res))
    .then((body) => body.count);
}

export function getMeme(id: string): Promise<MemeResponse> {
  return fetch(`${API_BASE_URL}/memes/${id}`).then((res) => handle<MemeResponse>(res));
}

export function searchText(query: string, category: string | null, topK = 12): Promise<SearchResultItem[]> {
  return fetch(`${API_BASE_URL}/search/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, topK, category }),
  }).then((res) => handle<SearchResultItem[]>(res));
}

export function searchImage(file: File, category: string | null, topK = 12): Promise<SearchResultItem[]> {
  const form = new FormData();
  form.set("image", file);
  form.set("topK", String(topK));
  if (category) form.set("category", category);
  return fetch(`${API_BASE_URL}/search/image`, { method: "POST", body: form }).then((res) =>
    handle<SearchResultItem[]>(res),
  );
}

export function recordView(id: string): Promise<void> {
  return fetch(`${API_BASE_URL}/memes/${id}/view`, { method: "POST" }).then((res) => handle<void>(res));
}

// Protected - upload/edit/delete, require an Entra token with the Admin role.

export async function updateMeme(id: string, updates: UpdateMemePayload): Promise<MemeResponse> {
  return fetch(`${API_BASE_URL}/memes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(updates),
  }).then((res) => handle<MemeResponse>(res));
}

export async function deleteMeme(id: string): Promise<void> {
  return fetch(`${API_BASE_URL}/memes/${id}`, { method: "DELETE", headers: await authHeaders() }).then((res) =>
    handle<void>(res),
  );
}

export async function ingestMeme(
  file: File,
  category: string,
  templateName: string,
  sourceUrl: string,
): Promise<IngestResponse> {
  const form = new FormData();
  form.set("image", file);
  form.set("category", category);
  if (templateName) form.set("templateName", templateName);
  if (sourceUrl) form.set("sourceUrl", sourceUrl);
  return fetch(`${API_BASE_URL}/memes`, { method: "POST", headers: await authHeaders(), body: form }).then((res) =>
    handle<IngestResponse>(res),
  );
}
