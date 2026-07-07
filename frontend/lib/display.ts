import type { MemeResponse, SearchResultItem } from "./api";

export interface DisplayMeme {
  id: string;
  templateName: string;
  tags: string[];
  category: string;
  ocrText?: string;
  caption?: string;
  similarity?: number;
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
    caption: item.caption,
    similarity: item.similarity,
  };
}
