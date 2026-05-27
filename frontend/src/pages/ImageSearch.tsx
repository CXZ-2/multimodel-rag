import { useState } from "react";
import { Upload, Button, Card, Typography, Tag, message, Image, Popconfirm } from "antd";
import {
  PictureOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { imageSearch, deleteDocument, type ImageSearchResult } from "../services/api";
import Sidebar from "../components/Sidebar";
import { toBase64 } from "../constants";

const { Dragger } = Upload;
const { Text } = Typography;

export default function ImageSearchPage() {
  const [results, setResults] = useState<ImageSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState("");

  const handleSearch = async (file: File) => {
    setLoading(true);
    const base64 = await toBase64(file);
    const previewUrl = `data:image/png;base64,${base64}`;
    setPreview(previewUrl);
    try {
      const res = await imageSearch({ image_base64: base64, top_k: 10 });
      setResults(res.results);
      if (res.results.length === 0) {
        message.info("未找到相似图片");
      } else {
        message.success(`找到 ${res.results.length} 张相似图片`);
      }
    } catch {
      message.error("搜索失败");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!docId) return;
    try {
      await deleteDocument(docId);
      message.success("已删除");
      setResults((prev) => prev.filter((r) => r.doc_id !== docId));
    } catch {
      message.error("删除失败");
    }
  };

  return (
    <div className="app-shell">
      <Sidebar />

      <main className="app-main">
        <header className="app-header">
          <Text style={{ color: "var(--text)", fontWeight: 600 }}>以图搜图</Text>
        </header>

        <div className="app-content" style={{ maxWidth: 900, margin: "0 auto" }}>
          {!preview && (
            <Dragger
              accept="image/*"
              maxCount={1}
              showUploadList={false}
              beforeUpload={handleSearch}
              disabled={loading}
              className="custom-dragger"
            >
              <PictureOutlined style={{ fontSize: 48, color: "var(--primary)" }} />
              <p style={{ fontSize: 15, fontWeight: 600, marginTop: 12 }}>
                上传图片，从知识库中搜索相似图片
              </p>
              <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
                使用 Chinese-CLIP 多模态向量检索 · 支持 JPG、PNG 格式
              </p>
            </Dragger>
          )}

          {preview && (
            <div style={{ marginBottom: 24, textAlign: "center" }}>
              <img src={preview} alt="query" style={{
                maxWidth: 320, maxHeight: 220,
                borderRadius: 12, border: "2px solid var(--primary-soft)",
                objectFit: "contain",
              }} />
              <div style={{ marginTop: 10 }}>
                <Button onClick={() => { setPreview(""); setResults([]); }}>
                  重新上传
                </Button>
              </div>
            </div>
          )}

          {loading && (
            <Card loading style={{ marginTop: 16 }} />
          )}

          {results.length > 0 && (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 12,
            }}>
              {results.map((r, i) => (
                <Card
                  key={i}
                  size="small"
                  hoverable
                  cover={
                    r.image_url ? (
                      <Image
                        src={r.image_url}
                        alt={r.doc_name}
                        style={{ height: 150, objectFit: "cover" }}
                        fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHRleHQgeD0iNSUiIHk9IjUwJSIgZm9udC1zaXplPSIxMiIgZmlsbD0iIzk5OSI+5Zu+54mH5Yqg6L295aSx6LSlPC90ZXh0Pjwvc3ZnPg=="
                        preview={{ mask: "点击查看大图" }}
                      />
                    ) : (
                      <div style={{
                        height: 150, background: "var(--bg-surface)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <PictureOutlined style={{ fontSize: 40, color: "var(--text-muted)", opacity: 0.3 }} />
                      </div>
                    )
                  }
                >
                  <Text style={{ fontSize: 12, fontWeight: 500 }} ellipsis>
                    {r.doc_name}
                  </Text>
                  <div style={{ marginTop: 4, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <Tag color="green" style={{ fontSize: 10 }}>第{r.page}页</Tag>
                      <Tag color="blue" style={{ fontSize: 10 }}>
                        {(r.score * 100).toFixed(0)}%
                      </Tag>
                    </div>
                    <Popconfirm
                      title="确认删除此文档？"
                      onConfirm={() => handleDelete(r.doc_id)}
                      placement="topRight"
                    >
                      <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
