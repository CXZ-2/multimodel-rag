import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Upload, Button, Typography, message, Tag, Space } from "antd";
import {
  InboxOutlined,
  CheckCircleOutlined,
  CloudUploadOutlined,
  RocketOutlined,
  LoadingOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  DeleteOutlined,
  GlobalOutlined,
} from "@ant-design/icons";
import type { UploadProps } from "antd";
import { uploadDocuments, getDocumentStatus, type DocumentInfo } from "../services/api";
import Sidebar from "../components/Sidebar";
import CrawlModal from "../components/CrawlModal";
import { STATUS_MAP } from "../constants";

const { Dragger } = Upload;
const { Title, Text } = Typography;

export default function UploadPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<DocumentInfo[]>(() => {
    try {
      const saved = localStorage.getItem("upload_results");
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [crawlOpen, setCrawlOpen] = useState(false);

  // Persist results to localStorage
  useEffect(() => {
    localStorage.setItem("upload_results", JSON.stringify(results));
  }, [results]);

  // Poll status for in-progress documents
  useEffect(() => {
    const pending = results.filter((d) => !["done", "failed"].includes(d.status));
    if (!pending.length) return;
    const timer = setInterval(async () => {
      const updated = await Promise.all(
        pending.map(async (d) => {
          try {
            const s = await getDocumentStatus(d.id);
            return { ...d, status: s.status, text_chunks: s.text_chunks, image_count: s.image_count, error_message: s.error_message };
          } catch { return d; }
        })
      );
      setResults(updated);
    }, 2000);
    return () => clearInterval(timer);
  }, [results]);

  const handleUpload: UploadProps["customRequest"] = async (options) => {
    const files = (Array.isArray(options.file) ? options.file : [options.file]) as File[];
    setUploading(true);
    setResults([]);
    try {
      const docs = await uploadDocuments(files);
      setResults(docs);
      message.success(`${docs.length} 个文件已提交处理`);
      options.onSuccess?.(docs);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? e?.message ?? "上传失败";
      message.error(msg);
      options.onError?.(e);
    } finally {
      setUploading(false);
    }
  };

  const doneCount = results.filter((d) => d.status === "done").length;
  const failedCount = results.filter((d) => d.status === "failed").length;
  const pendingCount = results.filter((d) => !["done", "failed"].includes(d.status)).length;

  return (
    <div className="app-shell">
      <Sidebar />

      {/* Main */}
      <main className="app-main">
        <header className="app-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Text style={{ color: "var(--text-muted)", fontSize: 13 }}>文档管理</Text>
            <Text style={{ color: "var(--border)", fontSize: 13 }}>/</Text>
            <Text style={{ color: "var(--text)", fontSize: 13, fontWeight: 600 }}>上传 PDF</Text>
          </div>
          <Space size={8}>
            <Button icon={<GlobalOutlined />} onClick={() => setCrawlOpen(true)}>网页爬取</Button>
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => navigate("/chat")}
            >
              进入问答
            </Button>
          </Space>
        </header>

        <div className="app-content">
          {/* Upload Card */}
          <div className="upload-card">
            <div className="upload-card-header">
              <div>
                <Text strong style={{ fontSize: 15, color: "var(--text)" }}>
                  上传 PDF 文档
                </Text>
                <Text style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: 10 }}>
                  支持批量选择 · 拖拽多个文件 · 异步处理
                </Text>
              </div>
              <Tag color="blue" style={{ borderRadius: 6 }}>最大 500MB / 文件</Tag>
            </div>

            <div className="upload-card-body">
              <Dragger
                accept=".pdf,.docx,.pptx,.xlsx,.md,.html,.jpg,.jpeg,.png,.bmp,.webp"
                multiple
                maxCount={20}
                showUploadList={false}
                customRequest={handleUpload}
                disabled={uploading}
                className="custom-dragger"
              >
                <InboxOutlined style={{
                  fontSize: 52,
                  color: "#d1d5db",
                  transition: "all var(--transition)",
                }} />
                <p style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: "var(--text)",
                  margin: "12px 0 4px",
                }}>
                  点击或拖拽 PDF 文件到此区域
                </p>
                <p style={{
                  fontSize: 12,
                  color: "var(--text-muted)",
                  lineHeight: 1.6,
                  maxWidth: 340,
                  margin: "0 auto",
                }}>
                  支持一次上传多个 PDF · 系统将异步完成
                  文字提取、图片识别 (OCR)、数据清理、向量索引
                </p>
              </Dragger>

              {/* Uploading indicator */}
              {uploading && (
                <div style={{
                  marginTop: 20,
                  background: "var(--primary-light)",
                  border: "1px solid var(--primary-soft)",
                  borderRadius: "var(--radius)",
                  padding: "16px 20px",
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                }}>
                  <div style={{
                    width: 40,
                    height: 40,
                    borderRadius: 11,
                    background: "var(--primary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    animation: "pulse-ring 2s infinite",
                  }}>
                    <CloudUploadOutlined style={{ color: "#fff", fontSize: 18 }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <Text strong style={{ fontSize: 14, color: "var(--text)" }}>
                      正在提交文件...
                    </Text>
                    <div style={{
                      marginTop: 8,
                      height: 4,
                      borderRadius: 2,
                      background: "var(--primary-soft)",
                      overflow: "hidden",
                    }}>
                      <div className="skeleton-shimmer" style={{ height: "100%", borderRadius: 2 }} />
                    </div>
                  </div>
                </div>
              )}

              {/* File Queue / Results */}
              {results.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 14,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      {doneCount === results.length
                        ? <CheckCircleOutlined style={{ fontSize: 18, color: "#10b981" }} />
                        : <LoadingOutlined style={{ fontSize: 18, color: "var(--primary)" }} />
                      }
                      <Text strong style={{ fontSize: 15, color: "var(--text)" }}>
                        {doneCount === results.length
                          ? `全部完成 · ${results.length} 个文件`
                          : `处理中 · ${doneCount}/${results.length} 完成${failedCount > 0 ? ` · ${failedCount} 失败` : ""}`}
                      </Text>
                    </div>
                    <Space size={8}>
                      <Button
                        size="small"
                        onClick={() => navigate("/knowledge")}
                        style={{ borderRadius: 8 }}
                      >
                        知识库管理
                      </Button>
                      <Button
                        size="small"
                        onClick={() => { setResults([]); localStorage.removeItem("upload_results"); }}
                        style={{ borderRadius: 8 }}
                      >
                        清除记录
                      </Button>
                    </Space>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {results.map((doc) => {
                      const statusInfo = STATUS_MAP[doc.status] || STATUS_MAP.pending;
                      return (
                        <div
                          key={doc.id}
                          style={{
                            background: "var(--bg-base)",
                            border: "1px solid var(--border-light)",
                            borderRadius: "var(--radius-sm)",
                            padding: "12px 16px",
                            display: "flex",
                            alignItems: "center",
                            gap: 12,
                          }}
                        >
                          <div style={{
                            width: 36,
                            height: 36,
                            borderRadius: 9,
                            background: doc.status === "done" ? "#ecfdf5" : doc.status === "failed" ? "#fef2f2" : "#eff3ff",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}>
                            {doc.status === "done" ? (
                              <CheckCircleOutlined style={{ color: "#10b981", fontSize: 16 }} />
                            ) : doc.status === "failed" ? (
                              <CloseCircleOutlined style={{ color: "#ef4444", fontSize: 16 }} />
                            ) : (
                              <SyncOutlined spin style={{ color: "var(--primary)", fontSize: 16 }} />
                            )}
                          </div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <Text style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>
                                {doc.filename}
                              </Text>
                              <Tag color={statusInfo.color} style={{ margin: 0, fontSize: 10 }}>
                                {statusInfo.icon} {statusInfo.label}
                              </Tag>
                            </div>
                            {doc.status === "done" && (
                              <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>
                                {doc.text_chunks} 个文本块 · {doc.image_count} 张图片
                              </Text>
                            )}
                            {doc.status === "failed" && doc.error_message && (
                              <Text type="danger" style={{ fontSize: 11 }}>
                                {doc.error_message}
                              </Text>
                            )}
                            {!["done", "failed"].includes(doc.status) && (
                              <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>
                                异步处理中...
                              </Text>
                            )}
                          </div>
                          <div style={{ width: 80, flexShrink: 0, textAlign: "right" }}>
                            <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>
                              {(doc.file_size / 1024).toFixed(0)} KB
                            </Text>
                          </div>
                          <Button
                            type="text"
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={() => {
                              const next = results.filter((d) => d.id !== doc.id);
                              setResults(next);
                              if (next.length === 0) localStorage.removeItem("upload_results");
                            }}
                            style={{ color: "var(--text-muted)", flexShrink: 0 }}
                          />
                        </div>
                      );
                    })}
                  </div>

                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      <CrawlModal open={crawlOpen} onClose={() => setCrawlOpen(false)} />
    </div>
  );
}
