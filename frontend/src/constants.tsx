import type { ReactNode } from "react";
import {
  SyncOutlined, CheckCircleOutlined, CloseCircleOutlined,
  CloudUploadOutlined, PictureOutlined, SearchOutlined, DatabaseOutlined,
} from "@ant-design/icons";

export const ROUTES = {
  UPLOAD: "/upload",
  IMAGE_SEARCH: "/image-search",
  CHAT: "/chat",
  KNOWLEDGE: "/knowledge",
} as const;

export const STATUS_MAP: Record<string, { color: string; icon: ReactNode; label: string }> = {
  pending: { color: "default", icon: <SyncOutlined />, label: "等待中" },
  cleaning: { color: "processing", icon: <SyncOutlined spin />, label: "清理中" },
  embedding: { color: "processing", icon: <SyncOutlined spin />, label: "嵌入中" },
  indexing: { color: "processing", icon: <SyncOutlined spin />, label: "索引中" },
  processing: { color: "processing", icon: <SyncOutlined spin />, label: "处理中" },
  generating: { color: "processing", icon: <SyncOutlined spin />, label: "生成中" },
  done: { color: "success", icon: <CheckCircleOutlined />, label: "完成" },
  failed: { color: "error", icon: <CloseCircleOutlined />, label: "失败" },
};

export const NAV_ITEMS = [
  { path: ROUTES.UPLOAD, icon: <CloudUploadOutlined className="sidebar-nav-icon" />, label: "文档上传" },
  { path: ROUTES.IMAGE_SEARCH, icon: <PictureOutlined className="sidebar-nav-icon" />, label: "以图搜图" },
  { path: ROUTES.CHAT, icon: <SearchOutlined className="sidebar-nav-icon" />, label: "智能问答" },
  { path: ROUTES.KNOWLEDGE, icon: <DatabaseOutlined className="sidebar-nav-icon" />, label: "知识库管理" },
];

export function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(",")[1] || "";
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
