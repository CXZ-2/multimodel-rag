import { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Button, Table, Tag, Typography, Space, message, Upload, Drawer,
  Empty, Popconfirm,
} from "antd";
import {
  CloudUploadOutlined, SearchOutlined, DatabaseOutlined,
  DeleteOutlined,
  FilePdfOutlined, ReloadOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
  GlobalOutlined, PictureOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { listDocuments, uploadDocuments, getDocumentStatus, deleteDocument, batchDeleteDocuments, type DocumentInfo } from "../services/api";
import Sidebar from "../components/Sidebar";
import CrawlModal from "../components/CrawlModal";
import { STATUS_MAP } from "../constants";

const { Title, Text } = Typography;

export default function KnowledgeBase() {
  const navigate = useNavigate();
  const location = useLocation();
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentInfo | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [crawlOpen, setCrawlOpen] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDocuments({ page_size: 50 });
      setDocs(res.items);
      setTotal(res.total);
    } catch { message.error("获取文档列表失败"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  // Poll status for in-progress docs (parallelized)
  useEffect(() => {
    const pendingDocs = docs.filter((d) => !["done", "failed"].includes(d.status));
    if (!pendingDocs.length) return;
    const timer = setInterval(async () => {
      const results = await Promise.all(
        pendingDocs.map(async (d) => {
          try {
            const s = await getDocumentStatus(d.id);
            return s.status;
          } catch { return d.status; }
        })
      );
      const changed = results.some((s, i) => s !== pendingDocs[i].status);
      if (changed) fetchDocs();
    }, 2000);
    return () => clearInterval(timer);
  }, [docs, fetchDocs]);

  const handleUpload = async (options: any) => {
    const files = Array.isArray(options.file) ? options.file : [options.file];
    setUploading(true);
    try {
      const res = await uploadDocuments(files);
      message.success(`${res.length} 个文件已提交处理`);
      await fetchDocs();
      options.onSuccess?.(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "上传失败");
      options.onError?.(e);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
      message.success("已删除");
      fetchDocs();
    } catch { message.error("删除失败"); }
  };

  const handleBatchDelete = async () => {
    try {
      const ids = selectedRowKeys.map(String);
      const res = await batchDeleteDocuments(ids);
      message.success(`已删除 ${res.deleted} 个文档`);
      setSelectedRowKeys([]);
      fetchDocs();
    } catch { message.error("批量删除失败"); }
  };


  const columns: ColumnsType<DocumentInfo> = [
    {
      title: "文件名", dataIndex: "filename", key: "filename",
      render: (name: string, record: DocumentInfo) => {
        if (record.source_type === "crawled" && record.source_url) {
          return (
            <a href={record.source_url} target="_blank" rel="noopener noreferrer">
              <FilePdfOutlined style={{ marginRight: 8, color: "#3b82f6" }} />
              {name}
            </a>
          );
        }
        return (
          <a onClick={() => { setSelectedDoc(record); setDrawerOpen(true); }}>
            <FilePdfOutlined style={{ marginRight: 8, color: "#ef4444" }} />
            {name}
          </a>
        );
      },
    },
    {
      title: "大小", dataIndex: "file_size", key: "file_size", width: 100,
      render: (s: number) => {
        const mb = s / 1024 / 1024;
        return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(s / 1024).toFixed(0)} KB`;
      },
    },
    {
      title: "状态", dataIndex: "status", key: "status", width: 120,
      render: (s: string) => {
        const m = STATUS_MAP[s] || STATUS_MAP.pending;
        return <Tag color={m.color} icon={m.icon}>{m.label}</Tag>;
      },
    },
    {
      title: "文本块", dataIndex: "text_chunks", key: "text_chunks", width: 80,
    },
    {
      title: "图片", dataIndex: "image_count", key: "image_count", width: 60,
    },
    {
      title: "来源", dataIndex: "source_type", key: "source_type", width: 90,
      render: (t: string) => {
        if (t === "crawled") return <Tag color="purple">网页爬取</Tag>;
        return <Tag color="default">上传</Tag>;
      },
    },
    {
      title: "上传时间", dataIndex: "uploaded_at", key: "uploaded_at", width: 160,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作", key: "actions", width: 80,
      render: (_: any, record: DocumentInfo) => (
        <Popconfirm title="确认删除此文档？" onConfirm={() => handleDelete(record.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className="app-shell">
      <Sidebar statusText={`${total} 个文档`} />

      {/* Main */}
      <main className="app-main">
        <header className="app-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Text style={{ color: "var(--text-muted)", fontSize: 13 }}>知识库</Text>
            <Text style={{ color: "var(--border)", fontSize: 13 }}>/</Text>
            <Text style={{ color: "var(--text)", fontSize: 13, fontWeight: 600 }}>文档管理</Text>
          </div>
          <Space>
            {selectedRowKeys.length > 0 && (
              <Popconfirm
                title={`确认删除选中的 ${selectedRowKeys.length} 个文档？此操作不可恢复`}
                onConfirm={handleBatchDelete}
              >
                <Button danger icon={<DeleteOutlined />}>
                  已选 {selectedRowKeys.length} 项 · 批量删除
                </Button>
              </Popconfirm>
            )}
            <Upload accept=".pdf,.docx,.pptx,.xlsx,.md,.html,.jpg,.jpeg,.png,.bmp,.webp" multiple showUploadList={false} customRequest={handleUpload}>
              <Button type="primary" icon={<CloudUploadOutlined />} loading={uploading}>
                批量上传
              </Button>
            </Upload>
            <Button icon={<GlobalOutlined />} onClick={() => setCrawlOpen(true)}>网页爬取</Button>
            <Button icon={<ReloadOutlined />} onClick={fetchDocs}>刷新</Button>
          </Space>
        </header>

        <div className="app-content">
          <Table
            columns={columns}
            dataSource={docs}
            rowKey="id"
            loading={loading}
            size="middle"
            locale={{ emptyText: <Empty description="暂无文档，点击「批量上传」添加" /> }}
            pagination={{ pageSize: 20, total, showSizeChanger: false }}
            style={{ background: "#fff", borderRadius: "var(--radius)", overflow: "hidden" }}
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys),
            }}
          />
        </div>
      </main>

      {/* Document Detail Drawer */}
      <Drawer
        title={selectedDoc?.filename}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={480}
        extra={selectedDoc && (
          <Popconfirm title="确认删除此文档？" onConfirm={() => { handleDelete(selectedDoc.id); setDrawerOpen(false); }}>
            <Button danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        )}
      >
        {selectedDoc && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", gap: 12 }}>
              <div style={{ flex: 1, background: "#f9fafb", borderRadius: 10, padding: "12px 16px", textAlign: "center" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{selectedDoc.text_chunks}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>文本块</div>
              </div>
              <div style={{ flex: 1, background: "#f9fafb", borderRadius: 10, padding: "12px 16px", textAlign: "center" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{selectedDoc.image_count}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>图片</div>
              </div>
              <div style={{ flex: 1, background: "#f9fafb", borderRadius: 10, padding: "12px 16px", textAlign: "center" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{(selectedDoc.file_size / 1024 / 1024).toFixed(1)}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>MB</div>
              </div>
            </div>

            <div>
              <Text strong>状态</Text>
              <Tag color={STATUS_MAP[selectedDoc.status]?.color} style={{ marginLeft: 8 }}>
                {STATUS_MAP[selectedDoc.status]?.label}
              </Tag>
            </div>

            {selectedDoc.cleaning_report && Object.keys(selectedDoc.cleaning_report).length > 0 && (
              <div>
                <Text strong>清理报告</Text>
                <div style={{
                  marginTop: 8, background: "#f0fdf4", borderRadius: 10,
                  border: "1px solid #bbf7d0", padding: "12px 16px",
                }}>
                  {selectedDoc.cleaning_report.headers_removed > 0 && (
                    <div>去除页眉/页脚: {selectedDoc.cleaning_report.headers_removed} 条</div>
                  )}
                  {selectedDoc.cleaning_report.noise_removed > 0 && (
                    <div>去除噪声行: {selectedDoc.cleaning_report.noise_removed} 条</div>
                  )}
                  {selectedDoc.cleaning_report.paragraphs_merged > 0 && (
                    <div>合并段落: {selectedDoc.cleaning_report.paragraphs_merged} 处</div>
                  )}
                  {selectedDoc.cleaning_report.duplicates_found > 0 && (
                    <div style={{ color: "#ef4444" }}>发现重复: {selectedDoc.cleaning_report.duplicates_found} 处</div>
                  )}
                  {selectedDoc.status === "done" &&
                    !selectedDoc.cleaning_report.headers_removed &&
                    !selectedDoc.cleaning_report.noise_removed &&
                    !selectedDoc.cleaning_report.paragraphs_merged && (
                      <div style={{ color: "#6b7280" }}>无需清理，文档格式良好</div>
                  )}
                </div>
              </div>
            )}

            {selectedDoc.error_message && (
              <div style={{ background: "#fef2f2", borderRadius: 10, border: "1px solid #fecaca", padding: "12px 16px" }}>
                <Text type="danger">{selectedDoc.error_message}</Text>
              </div>
            )}
          </div>
        )}
      </Drawer>

      <CrawlModal open={crawlOpen} onClose={() => setCrawlOpen(false)} onSuccess={fetchDocs} />
    </div>
  );
}
