import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// --- Existing ---
export interface UploadResponse {
  message: string;
  doc_id: string;
  collection_id: string;
  text_chunks: number;
  images: number;
}

export interface SourceItem {
  type: "text" | "image";
  index: number;
  content?: string;
  image_url?: string;
  page: number;
  score: number;
  doc_name: string;
}

export interface QueryResponse {
  answer: string;
  sources: SourceItem[];
}

export interface CollectionInfo {
  id: string;
  name: string;
  doc_count: number;
  created_at: string;
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<UploadResponse>("/upload", form);
  return data;
}

export async function queryRag(params: {
  question: string;
  conversation_id?: string;
  image_base64?: string;
  collection_id?: string;
  top_k?: number;
}): Promise<QueryResponse> {
  const { data } = await api.post<QueryResponse>("/query", params);
  return data;
}

export async function listCollections(): Promise<CollectionInfo[]> {
  const { data } = await api.get<CollectionInfo[]>("/collections");
  return data;
}

export async function deleteCollection(id: string): Promise<void> {
  await api.delete(`/collections/${id}`);
}

// --- Document Management ---
export interface DocumentInfo {
  id: string;
  filename: string;
  file_size: number;
  status: string;
  text_chunks: number;
  image_count: number;
  cleaning_report: Record<string, number>;
  error_message?: string;
  source_url?: string;
  source_type?: string;
  uploaded_at: string;
}

export interface DocumentListResponse {
  items: DocumentInfo[];
  total: number;
}

export interface DocumentStatusResponse {
  id: string;
  status: string;
  text_chunks: number;
  image_count: number;
  error_message?: string;
}

export async function uploadDocuments(files: File[]): Promise<DocumentInfo[]> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const { data } = await api.post<DocumentInfo[]>("/documents/upload", form);
  return data;
}

export async function listDocuments(params?: {
  status?: string;
  source_type?: string;
  page?: number;
  page_size?: number;
}): Promise<DocumentListResponse> {
  const { data } = await api.get<DocumentListResponse>("/documents", { params });
  return data;
}

export async function getDocumentStatus(id: string): Promise<DocumentStatusResponse> {
  const { data } = await api.get<DocumentStatusResponse>(`/documents/${id}/status`);
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`);
}

export async function batchDeleteDocuments(ids: string[]): Promise<{ ok: boolean; deleted: number; errors: string[] }> {
  const { data } = await api.post("/documents/batch-delete", { ids });
  return data;
}

// --- Conversation Management ---
export interface ConversationInfo {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface MessageInfo {
  id: string;
  role: string;
  content: string;
  image_base64?: string;
  sources?: any[];
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  messages: MessageInfo[];
  created_at: string;
}

export async function listConversations(): Promise<ConversationInfo[]> {
  const { data } = await api.get<ConversationInfo[]>("/conversations");
  return data;
}

export async function createConversation(): Promise<ConversationInfo> {
  const { data } = await api.post<ConversationInfo>("/conversations");
  return data;
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const { data } = await api.get<ConversationDetail>(`/conversations/${id}`);
  return data;
}

export async function deleteConversation(id: string): Promise<void> {
  await api.delete(`/conversations/${id}`);
}

export async function appendMessage(convId: string, body: {
  role?: string;
  content: string;
  sources?: any[];
  image_base64?: string;
}): Promise<MessageInfo> {
  const { data } = await api.post<MessageInfo>(`/conversations/${convId}/messages`, body);
  return data;
}

// --- Web Crawl ---
export interface CrawlRequest {
  source: string;
  limit: number;
  max_body_length?: number;
}

export interface CrawlResponse {
  crawled: number;
  skipped: number;
  items: { id: string; title: string; url: string }[];
}

export interface CrawlSource {
  name: string;
  base_url: string;
}

export async function crawlDocuments(req: CrawlRequest): Promise<CrawlResponse> {
  const { data } = await api.post<CrawlResponse>("/documents/crawl", req);
  return data;
}

export async function getCrawlSources(): Promise<Record<string, CrawlSource>> {
  const { data } = await api.get<Record<string, CrawlSource>>("/documents/crawl/sources");
  return data;
}

// --- 以图搜图 ---

export interface ImageSearchResult {
  doc_name: string;
  doc_id: string;
  image_url: string;
  page: number;
  score: number;
}

export async function imageSearch(params: {
  image_base64: string;
  top_k?: number;
}): Promise<{ results: ImageSearchResult[] }> {
  const { data } = await api.post("/image-search", params);
  return data;
}

// --- SSE 流式查询 ---
export async function queryRagStream(
  params: {
    question: string;
    conversation_id?: string;
    image_base64?: string;
  },
  onToken: (token: string) => void,
  onSources: (sources: SourceItem[]) => void,
  onAgent: (agent: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
  } catch (e: any) {
    onError(e);
    return;
  }

  if (!response.ok) {
    onError(new Error(`HTTP ${response.status}`));
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      let eventType = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7);
        } else if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            switch (eventType) {
              case "token":
                onToken(typeof data === "string" ? data : "");
                break;
              case "sources":
                onSources(Array.isArray(data) ? data : []);
                break;
              case "agent":
                onAgent(typeof data === "string" ? data : "");
                break;
              case "done":
                onDone();
                break;
            }
          } catch { /* skip malformed JSON */ }
          eventType = "";
        }
      }
    }
  } catch (e: any) {
    onError(e);
  }
}

// ========== 视频相关 ==========

export interface VideoUploadResponse {
  message: string;
  doc_id: string;
  status: string;
}

export interface VideoStatusResponse {
  id: string;
  status: string;
  duration: number | null;
  transcript: string | null;
  description: string | null;
  error_message: string | null;
}

export interface VideoInfo {
  id: string;
  filename: string;
  file_size: number;
  duration: number | null;
  status: string;
  source_type: string;
  understanding: any;
  uploaded_at: string;
}

export interface VideoListResponse {
  items: VideoInfo[];
  total: number;
}

export interface VideoGenerateRequest {
  prompt: string;
  model?: string;
  resolution?: string;
  ratio?: string;
  duration?: number;
  negative_prompt?: string;
}

export interface VideoGenerateResponse {
  task_id: string;
  status: string;
}

export interface VideoGenerateStatusResponse {
  task_id: string;
  status: string;
  video_url: string | null;
  error_message: string | null;
}

export async function uploadVideo(file: File): Promise<VideoUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<VideoUploadResponse>("/videos/upload", form);
  return data;
}

export async function getVideoStatus(docId: string): Promise<VideoStatusResponse> {
  const { data } = await api.get<VideoStatusResponse>(`/videos/${docId}/status`);
  return data;
}

export async function listVideos(params?: {
  status?: string;
  source_type?: string;
  page?: number;
  page_size?: number;
}): Promise<VideoListResponse> {
  const { data } = await api.get<VideoListResponse>("/videos", { params });
  return data;
}

export async function deleteVideo(docId: string): Promise<void> {
  await api.delete(`/videos/${docId}`);
}

export async function generateVideo(req: VideoGenerateRequest): Promise<VideoGenerateResponse> {
  const { data } = await api.post<VideoGenerateResponse>("/videos/generate", req);
  return data;
}

export async function getGenerationStatus(
  taskId: string,
  model?: string
): Promise<VideoGenerateStatusResponse> {
  const { data } = await api.get<VideoGenerateStatusResponse>(
    `/videos/generate/${taskId}`,
    { params: { model } }
  );
  return data;
}
