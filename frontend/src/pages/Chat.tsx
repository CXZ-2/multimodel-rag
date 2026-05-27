import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Input,
  Button,
  Card,
  Typography,
  Space,
  Tag,
  Upload,
  message,
  Popconfirm,
  Spin,
} from "antd";
import {
  SendOutlined,
  UploadOutlined,
  PictureOutlined,
  DeleteOutlined,
  RobotOutlined,
  UserOutlined,
  SettingOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  MessageOutlined,
  LoadingOutlined,
  QuestionCircleOutlined,
  CloudUploadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import type { UploadFile } from "antd";
import {
  queryRag,
  queryRagStream,
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  type QueryResponse,
  type ConversationInfo,
  type MessageInfo,
} from "../services/api";
import Sidebar from "../components/Sidebar";
import { toBase64 } from "../constants";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface Message {
  id: number;
  type: "user" | "assistant";
  content: string;
  sources?: QueryResponse["sources"];
  imagePreview?: string;
}

export default function ChatPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [imageFile, setImageFile] = useState<UploadFile | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Conversation state
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [convsLoading, setConvsLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());
  const [streamingContent, setStreamingContent] = useState("");

  const fetchConversations = useCallback(async (): Promise<ConversationInfo[]> => {
    setConvsLoading(true);
    try {
      const list = await listConversations();
      setConversations(list);
      return list;
    } catch { return []; }
    finally { setConvsLoading(false); }
  }, []);

  useEffect(() => {
    fetchConversations().then(async (list) => {
      // Auto-select the most recent conversation when returning to the page
      if (list && list.length > 0) {
        setActiveConvId(list[0].id);
        try {
          const detail = await getConversation(list[0].id);
          const msgs: Message[] = detail.messages.map((m: MessageInfo, idx: number) => ({
            id: idx,
            type: m.role as "user" | "assistant",
            content: m.content,
            sources: m.sources,
            imagePreview: m.image_base64 ? `data:image/png;base64,${m.image_base64}` : undefined,
          }));
          setMessages(msgs);
        } catch { /* ignore */ }
      }
    });
  }, [fetchConversations]);

  // Load conversation history when clicking a conversation
  const handleSelectConv = async (id: string) => {
    setActiveConvId(id);
    setExpandedSources(new Set());
    try {
      const detail = await getConversation(id);
      const msgs: Message[] = detail.messages.map((m: MessageInfo, idx: number) => ({
        id: idx,
        type: m.role as "user" | "assistant",
        content: m.content,
        sources: m.sources,
        imagePreview: m.image_base64 ? `data:image/png;base64,${m.image_base64}` : undefined,
      }));
      setMessages(msgs);
    } catch {
      message.error("加载会话失败");
    }
  };

  const handleNewConv = async () => {
    try {
      const conv = await createConversation();
      setConversations((prev) => [conv, ...prev]);
      setActiveConvId(conv.id);
      setMessages([]);
      setExpandedSources(new Set());
    } catch { message.error("创建会话失败"); }
  };

  const handleDeleteConv = async (id: string) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConvId === id) {
        setActiveConvId(null);
        setMessages([]);
      }
      message.success("会话已删除");
    } catch { message.error("删除失败"); }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, streamingContent]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question) return;

    // Auto-create conversation if none active
    let convId = activeConvId;
    if (!convId) {
      try {
        const conv = await createConversation();
        setConversations((prev) => [conv, ...prev]);
        convId = conv.id;
        setActiveConvId(convId);
      } catch {
        // query still works without conversation
      }
    }

    const userMsg: Message = {
      id: Date.now(),
      type: "user",
      content: question,
      imagePreview: imageFile?.thumbUrl || imageFile?.url,
    };

    const assistantMsgId = Date.now() + 1;

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setStreamingContent("");

    try {
      let imageBase64: string | undefined;
      if (imageFile?.originFileObj) {
        imageBase64 = await toBase64(imageFile.originFileObj);
      }

      // 先添加空的 assistant 消息占位
      setMessages((prev) => [
        ...prev,
        { id: assistantMsgId, type: "assistant" as const, content: "", sources: [] },
      ]);

      await queryRagStream(
        { question, image_base64: imageBase64, conversation_id: convId || undefined },
        // onToken
        (token) => {
          setStreamingContent((prev) => {
            const next = prev + token;
            setMessages((msgs) =>
              msgs.map((m) => (m.id === assistantMsgId ? { ...m, content: next } : m))
            );
            return next;
          });
        },
        // onSources
        (sources) => {
          setMessages((msgs) =>
            msgs.map((m) => (m.id === assistantMsgId ? { ...m, sources } : m))
          );
        },
        // onAgent
        () => {},
        // onDone
        () => {
          setLoading(false);
          setImageFile(null);
          setStreamingContent("");
          fetchConversations();
        },
        // onError
        (err) => {
          message.error(err.message || "查询失败");
          setLoading(false);
          setImageFile(null);
          setStreamingContent("");
        },
      );
    } catch (e: any) {
      message.error(e?.message ?? "查询失败");
      setLoading(false);
      setImageFile(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="app-shell">
      <Sidebar />

      {/* Conversation Sidebar */}
      <aside className="conv-sidebar">
        <div className="conv-sidebar-header">
          <span className="conv-sidebar-title">会话</span>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleNewConv}
            className="conv-new-btn"
          >
            新建
          </Button>
        </div>

        <div className="conv-list">
          {convsLoading ? (
            <div style={{ textAlign: "center", padding: 40 }}>
              <Spin indicator={<LoadingOutlined style={{ fontSize: 20 }} />} />
            </div>
          ) : conversations.length === 0 ? (
            <div className="conv-empty">
              <MessageOutlined style={{ fontSize: 28, color: "var(--text-muted)", opacity: 0.4 }} />
              <span>暂无会话</span>
            </div>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                className={`conv-item ${activeConvId === c.id ? "active" : ""}`}
                onClick={() => handleSelectConv(c.id)}
              >
                <div className="conv-item-main">
                  <div className="conv-item-title">
                    {c.title.length > 20 ? c.title.slice(0, 20) + "..." : c.title}
                  </div>
                  <div className="conv-item-meta">
                    {c.message_count} 条消息 · {new Date(c.updated_at).toLocaleDateString("zh-CN")}
                  </div>
                </div>
                <Popconfirm
                  title="确认删除此会话？"
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    handleDeleteConv(c.id);
                  }}
                  onCancel={(e) => e?.stopPropagation()}
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    className="conv-delete-btn"
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="app-main chat-main" style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        <header className="app-header">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Text style={{ color: "var(--text-muted)", fontSize: 13 }}>智能问答</Text>
            <Text style={{ color: "var(--border)", fontSize: 13 }}>/</Text>
            <Text style={{ color: "var(--text)", fontSize: 13, fontWeight: 600 }}>
              {messages.length > 0 ? `对话中 · ${messages.filter(m => m.type === 'assistant').length} 轮` : '新建会话'}
            </Text>
          </div>
          <Space>
            <Button
              type="text"
              icon={<QuestionCircleOutlined />}
              style={{ color: "var(--text-muted)" }}
            >
              帮助
            </Button>
            <Button
              icon={<CloudUploadOutlined />}
              onClick={() => navigate("/upload")}
            >
              上传文档
            </Button>
          </Space>
        </header>

        {/* Messages area */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "0 28px",
        }}>
          <div style={{ maxWidth: 860, margin: "0 auto" }}>
            {messages.length === 0 ? (
              /* Empty state */
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                paddingTop: "16vh",
              }}>
                <div style={{
                  width: 80,
                  height: 80,
                  borderRadius: 22,
                  background: "linear-gradient(135deg, #eff3ff, #e0e7ff)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 20,
                  boxShadow: "0 0 40px rgba(94,129,254,.1)",
                }}>
                  <RobotOutlined style={{ fontSize: 36, color: "var(--primary)" }} />
                </div>
                <Text strong style={{ fontSize: 18, color: "var(--text)", marginBottom: 6 }}>
                  {activeConvId ? "开始对话" : "开始多模态检索问答"}
                </Text>
                <Text style={{ fontSize: 14, color: "var(--text-secondary)", textAlign: "center", lineHeight: 1.7, maxWidth: 400 }}>
                  {activeConvId
                    ? "输入你的问题，系统将通过语义检索找到最相关的文本和图片，由 AI 生成准确回答"
                    : "新建一个会话或选择已有会话开始问答"}
                </Text>

                <div style={{ marginTop: 28, display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", maxWidth: 500 }}>
                  {[
                    { icon: <FileTextOutlined />, text: "总结文档主要内容" },
                    { icon: <SearchOutlined />, text: "帮我找出关键数据" },
                    { icon: <ThunderboltOutlined />, text: "文档的核心观点是什么" },
                  ].map((s, i) => (
                    <div
                      key={i}
                      onClick={() => { setInput(s.text); }}
                      style={{
                        padding: "8px 14px",
                        borderRadius: 20,
                        border: "1px solid var(--border)",
                        fontSize: 12,
                        color: "var(--text-secondary)",
                        cursor: "pointer",
                        transition: "all var(--transition)",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        background: "var(--bg-surface)",
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.borderColor = "var(--primary)";
                        (e.currentTarget as HTMLElement).style.color = "var(--primary)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                        (e.currentTarget as HTMLElement).style.color = "var(--text-secondary)";
                      }}
                    >
                      {s.icon} {s.text}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              /* Messages */
              <div style={{ padding: "24px 0" }}>
                {messages.map((msg, idx) => (
                  <div key={msg.id} className={`chat-message-row ${msg.type}`} style={{
                    animationDelay: `${idx * .03}s`,
                  }}>
                    <div className={`chat-avatar ${msg.type}`}>
                      {msg.type === "user" ? <UserOutlined /> : <RobotOutlined />}
                    </div>

                    <div className={`chat-bubble ${msg.type}`}>
                      {msg.imagePreview && (
                        <div style={{ marginBottom: 10 }}>
                          <img
                            src={msg.imagePreview}
                            alt="query"
                            style={{
                              maxWidth: 200,
                              maxHeight: 150,
                              borderRadius: 10,
                            }}
                          />
                        </div>
                      )}

                      {msg.type === "assistant" ? (
                        <>
                          <ReactMarkdown
                            components={{
                              p: ({ children }) => (
                                <Paragraph style={{ marginBottom: 8, fontSize: 13.5, lineHeight: 1.75, color: "var(--text)" }}>
                                  {children}
                                </Paragraph>
                              ),
                              strong: ({ children }) => <Text strong>{children}</Text>,
                              h3: ({ children }) => (
                                <Title level={5} style={{ margin: "10px 0 4px", fontSize: 15 }}>
                                  {children}
                                </Title>
                              ),
                              ul: ({ children }) => (
                                <ul style={{ paddingLeft: 18, marginBottom: 8 }}>{children}</ul>
                              ),
                              li: ({ children }) => (
                                <li style={{ marginBottom: 2, fontSize: 13.5, color: "var(--text-secondary)" }}>
                                  {children}
                                </li>
                              ),
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>

                          {msg.sources && msg.sources.length > 0 && (
                            <div className="sources-section">
                              <div
                                onClick={() => {
                                  setExpandedSources((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(msg.id)) {
                                      next.delete(msg.id);
                                    } else {
                                      next.add(msg.id);
                                    }
                                    return next;
                                  });
                                }}
                                style={{
                                  cursor: "pointer",
                                  userSelect: "none",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  padding: "6px 10px",
                                  borderRadius: 6,
                                  border: "1px solid var(--border-light)",
                                  background: expandedSources.has(msg.id) ? "var(--bg-surface)" : "var(--primary-light)",
                                  transition: "background var(--transition)",
                                }}
                              >
                                <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                                  参考来源 · 相似度最高的 {Math.min(3, msg.sources.length)} 条
                                </span>
                                <span style={{ fontSize: 11, color: "var(--primary)", fontWeight: 500 }}>
                                  {expandedSources.has(msg.id) ? "展开来源 ▼" : "收起 ▲"}
                                </span>
                              </div>
                              {!expandedSources.has(msg.id) && msg.sources.slice(0, 3).map((s, i) => {
                                const cleaned = s.content?.replace(/^[\s，,。、；;：:！!？?…·\.\-—]+/, "") ?? "";
                                return (
                                  <div key={i} className="source-item">
                                    <Space size={6} style={{ marginBottom: 4 }}>
                                      <Tag color={s.type === "text" ? "blue" : "green"} style={{ margin: 0, fontSize: 10 }}>
                                        [来源{s.index}]
                                      </Tag>
                                      {s.doc_name && (
                                        <Text style={{ fontSize: 10, color: "var(--text-muted)", maxWidth: 180 }} ellipsis>
                                          {s.doc_name}
                                        </Text>
                                      )}
                                      <Text style={{ fontSize: 10, color: "var(--text-muted)" }}>
                                        第 {s.page} 页 · {(s.score * 100).toFixed(0)}%
                                      </Text>
                                    </Space>
                                    {s.type === "text" && cleaned && (
                                      <Paragraph
                                        ellipsis={{ rows: 2, expandable: true, symbol: "展开" }}
                                        style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 0, lineHeight: 1.6 }}
                                      >
                                        {cleaned}
                                      </Paragraph>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </>
                      ) : (
                        <span>{msg.content}</span>
                      )}
                    </div>
                  </div>
                ))}

                {/* Typing indicator */}
                {loading && !streamingContent && (
                  <div className="chat-message-row assistant">
                    <div className="chat-avatar assistant">
                      <RobotOutlined />
                    </div>
                    <div className="chat-bubble assistant" style={{ display: "flex", gap: 6, padding: "16px 20px" }}>
                      {[0, 1, 2].map((i) => (
                        <div key={i} style={{
                          width: 7,
                          height: 7,
                          borderRadius: "50%",
                          background: "var(--primary)",
                          opacity: .35,
                          animation: `pulse-ring 1.4s ${i * .2}s infinite`,
                        }} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input bar */}
        <div style={{
          padding: "16px 28px 22px",
          background: "linear-gradient(180deg, transparent, var(--bg-base) 30%)",
        }}>
          <div style={{ maxWidth: 860, margin: "0 auto" }}>
            {imageFile && (
              <div style={{
                marginBottom: 10,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: "var(--primary-light)",
                border: "1px solid var(--primary-soft)",
                borderRadius: 20,
                padding: "5px 14px 5px 10px",
              }}>
                <PictureOutlined style={{ color: "var(--primary)", fontSize: 13 }} />
                <Text style={{ fontSize: 12, color: "var(--text)" }}>{imageFile.name}</Text>
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => setImageFile(null)}
                  style={{ color: "var(--text-muted)", minWidth: 20 }}
                />
              </div>
            )}

            <div className="chat-input-wrap">
              <Upload
                accept="image/*"
                maxCount={1}
                showUploadList={false}
                fileList={imageFile ? [imageFile] : []}
                beforeUpload={(file) => {
                  const reader = new FileReader();
                  reader.onload = (e) => {
                    setImageFile({
                      uid: "-1",
                      name: file.name,
                      url: e.target?.result as string,
                      thumbUrl: e.target?.result as string,
                      originFileObj: file,
                    });
                  };
                  reader.readAsDataURL(file);
                  return false;
                }}
                onRemove={() => setImageFile(null)}
              >
                <Button
                  type="text"
                  icon={<UploadOutlined />}
                  style={{
                    color: imageFile ? "var(--primary)" : "var(--text-muted)",
                    fontSize: 18,
                    width: 40,
                    height: 40,
                  }}
                />
              </Upload>

              <TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入问题，支持图文联合检索..."
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={loading}
                style={{
                  flex: 1,
                  border: "none",
                  resize: "none",
                  fontSize: 14,
                  lineHeight: 1.6,
                  padding: "10px 0",
                  boxShadow: "none",
                  background: "transparent",
                  outline: "none",
                }}
              />

              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                disabled={!input.trim()}
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 16,
                  flexShrink: 0,
                }}
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
