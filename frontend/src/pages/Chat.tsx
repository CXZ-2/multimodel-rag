import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Input,
  Button,
  Card,
  Popover,
  Typography,
  Space,
  Tag,
  Upload,
  message,
  Popconfirm,
  Spin,
  Select,
} from "antd";
import {
  SendOutlined,
  UploadOutlined,
  PictureOutlined,
  VideoCameraOutlined,
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
  uploadVideo,
  getVideoStatus,
  generateVideo as apiGenerateVideo,
  getGenerationStatus,
  appendMessage,
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
  const [videoFile, setVideoFile] = useState<UploadFile | null>(null);
  const [genPopOpen, setGenPopOpen] = useState(false);
  const [genPrompt, setGenPrompt] = useState("");
  const [genModel, setGenModel] = useState("wanx2.1-t2v-turbo");
  const [genRatio, setGenRatio] = useState("16:9");
  const [genDuration, setGenDuration] = useState(5);
  const [generatingVideo, setGeneratingVideo] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Conversation state
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(() => {
    return localStorage.getItem("chat_active_conv") || null;
  });
  const [convsLoading, setConvsLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());
  const [streamingContent, setStreamingContent] = useState("");

  // 持久化 activeConvId 到 localStorage，切换 tab 时恢复
  useEffect(() => {
    if (activeConvId) {
      localStorage.setItem("chat_active_conv", activeConvId);
    } else {
      localStorage.removeItem("chat_active_conv");
    }
  }, [activeConvId]);

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
    // 恢复之前生成的视频
    const savedVideos = JSON.parse(localStorage.getItem("gen_videos") || "[]");
    if (savedVideos.length > 0) {
      const videoMsgs: Message[] = savedVideos.map((v: any, i: number) => ({
        id: Date.now() - savedVideos.length + i,
        type: "assistant" as const,
        content: `已根据你的描述生成视频：\n\n[点击播放视频](/api/videos/proxy?url=${encodeURIComponent(v.url)})\n\n> 提示：*${v.prompt}*`,
      }));
      setMessages(videoMsgs);
    }

    fetchConversations().then(async (list) => {
      if (list && list.length > 0) {
        // 优先恢复上次选中的会话，其次选最新
        const savedConvId = localStorage.getItem("chat_active_conv");
        const targetId = savedConvId && list.some(c => c.id === savedConvId)
          ? savedConvId
          : list[0].id;
        setActiveConvId(targetId);
        try {
          const detail = await getConversation(targetId);
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

  const handleVideoUpload = async (file: any) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setVideoFile({
        uid: "-1", name: file.name,
        url: e.target?.result as string,
        thumbUrl: e.target?.result as string,
        originFileObj: file,
      });
    };
    reader.readAsDataURL(file);

    // 自动创建对话（如果没有激活的）
    let convId = activeConvId;
    if (!convId) {
      try {
        const conv = await createConversation();
        setConversations((prev) => [conv, ...prev]);
        convId = conv.id;
        setActiveConvId(convId);
      } catch { /* 无对话也能上传 */ }
    }

    // 自动在聊天中添加消息
    const userContent = `我上传了一个视频：${file.name}`;
    const userMsg: Message = { id: Date.now(), type: "user", content: userContent };
    const statusMsgId = Date.now() + 1;
    const statusMsg: Message = { id: statusMsgId, type: "assistant", content: `📤 视频 "${file.name}" 已上传，正在后台处理中...` };
    setMessages((prev) => [...prev, userMsg, statusMsg]);

    // 保存用户消息到后端
    let userBackendId: string | null = null;
    if (convId) {
      try {
        const saved = await appendMessage(convId, { role: "user", content: userContent });
        userBackendId = saved.id;
      } catch { /* 非关键 */ }
    }

    try {
      const res = await uploadVideo(file);
      const docId = res.doc_id;
      // 轮询处理状态
      const poll = setInterval(async () => {
        try {
          const s = await getVideoStatus(docId);
          if (s.status === "done") {
            clearInterval(poll);
            const desc = s.description ? `\n\n> 内容概要：${s.description.slice(0, 200)}` : "";
            const doneContent = `✅ 视频 "${file.name}" 已处理完成！${desc}\n\n你可以问我关于这个视频的任何问题。`;
            setMessages((msgs) => msgs.map((m) =>
              m.id === statusMsgId ? { ...m, content: doneContent } : m
            ));
            // 保存完成消息到后端
            if (convId) {
              try {
                await appendMessage(convId, {
                  role: "assistant", content: doneContent,
                  sources: [{ type: "video", doc_id: docId, filename: file.name, description: s.description }],
                });
              } catch { /* 非关键 */ }
            }
            message.success(`视频 ${file.name} 处理完成`);
          } else if (s.status === "failed") {
            clearInterval(poll);
            const failContent = `❌ 视频 "${file.name}" 处理失败：${s.error_message || "未知错误"}`;
            setMessages((msgs) => msgs.map((m) =>
              m.id === statusMsgId ? { ...m, content: failContent } : m
            ));
          } else if (s.status === "processing") {
            setMessages((msgs) => msgs.map((m) =>
              m.id === statusMsgId
                ? { ...m, content: `🔍 正在理解视频内容... (${file.name})` }
                : m
            ));
          }
        } catch (err: any) {
          // 404 = 视频已被删除，停止轮询
          if (err?.response?.status === 404) {
            clearInterval(poll);
            setMessages((msgs) => msgs.filter((m) => m.id !== statusMsgId));
          }
          /* 其他网络错误继续轮询 */
        }
      }, 3000);
    } catch (e: any) {
      setMessages((msgs) => msgs.map((m) =>
        m.id === statusMsgId ? { ...m, content: `❌ 视频上传失败：${e?.response?.data?.detail || "未知错误"}` } : m
      ));
    }
    return false;
  };

  const handleVideoGenerate = async () => {
    if (!genPrompt.trim()) {
      message.warning("请输入视频描述");
      return;
    }
    setGeneratingVideo(true);
    setGenPopOpen(false);
    const genPromptText = genPrompt;
    setGenPrompt("");

    // 先添加一条"生成中"的助手消息，显示进度
    const progressMsgId = Date.now();
    const progressMsg: Message = {
      id: progressMsgId,
      type: "assistant",
      content: `正在根据描述生成视频：*${genPromptText}*\n\n状态：⏳ 创建任务中...`,
    };
    setMessages((prev) => [...prev, progressMsg]);

    try {
      const res = await apiGenerateVideo({
        prompt: genPromptText, model: genModel,
        ratio: genRatio, duration: genDuration,
      });

      // 更新进度消息
      const updateProgress = (status: string) => {
        setMessages((msgs) => msgs.map((m) =>
          m.id === progressMsgId
            ? { ...m, content: `正在根据描述生成视频：*${genPromptText}*\n\n状态：${status}` }
            : m
        ));
      };

      updateProgress(`⏳ 任务排队中... (${res.task_id.slice(0, 8)})`);

      // 轮询等待完成，及时更新进度
      const poll = setInterval(async () => {
        try {
          const status = await getGenerationStatus(res.task_id, genModel);
          if (status.status === "SUCCEEDED" && status.video_url) {
            clearInterval(poll);
            setGeneratingVideo(false);
            // 替换进度消息为完成的视频
            const proxyUrl = `/api/videos/proxy?url=${encodeURIComponent(status.video_url)}`;
            const videoContent = `已根据你的描述生成视频：\n\n[点击播放视频](${proxyUrl})\n\n> 提示：*${genPromptText}*`;
            setMessages((msgs) => msgs.map((m) =>
              m.id === progressMsgId
                ? { ...m, content: videoContent }
                : m
            ));
            // 持久化到 localStorage
            const saved = JSON.parse(localStorage.getItem("gen_videos") || "[]");
            saved.push({ prompt: genPromptText, url: status.video_url, taskId: res.task_id, time: Date.now() });
            localStorage.setItem("gen_videos", JSON.stringify(saved.slice(-20)));
            // 保存到后端对话
            if (activeConvId) {
              try {
                await appendMessage(activeConvId, {
                  role: "assistant",
                  content: videoContent,
                  sources: [{ type: "video", url: status.video_url, prompt: genPromptText }],
                });
              } catch { /* 非关键 */ }
            }
            message.success("视频生成完成！");
          } else if (status.status === "FAILED") {
            clearInterval(poll);
            setGeneratingVideo(false);
            updateProgress(`❌ 生成失败：${status.error_message || "未知错误"}`);
            message.error(status.error_message || "视频生成失败");
          } else if (status.status === "RUNNING") {
            updateProgress(`🎬 AI 正在生成视频中... 通常需要 1-3 分钟`);
          }
        } catch { /* 继续轮询 */ }
      }, 5000);
    } catch (e: any) {
      setGeneratingVideo(false);
      const errMsg = e?.response?.data?.detail || "生成失败";
      setMessages((msgs) => msgs.map((m) =>
        m.id === progressMsgId
          ? { ...m, content: `视频生成失败：${errMsg}\n\n> 提示：*${genPromptText}*` }
          : m
      ));
      message.error(errMsg);
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
                    { icon: <VideoCameraOutlined />, text: "上传视频并分析内容" },
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
                              img: ({ src, alt }) => {
                                if (src && /\.(mp4|mov|webm)(\?|$)/i.test(src)) {
                                  return (
                                    <video src={src} controls style={{ maxWidth: "100%", maxHeight: 320, borderRadius: 10, margin: "8px 0" }}>
                                      你的浏览器不支持视频播放
                                    </video>
                                  );
                                }
                                return <img src={src} alt={alt} style={{ maxWidth: 200, maxHeight: 150, borderRadius: 10 }} />;
                              },
                              a: ({ href, children }) => {
                                if (href && /\.(mp4|mov|webm)(\?|$)/i.test(href)) {
                                  return (
                                    <video src={href} controls style={{ maxWidth: "100%", maxHeight: 320, borderRadius: 10, margin: "8px 0" }}>
                                      你的浏览器不支持视频播放
                                    </video>
                                  );
                                }
                                return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
                              },
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
            {(imageFile || videoFile) && (
              <div style={{ marginBottom: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {imageFile && (
                  <div style={{
                    display: "inline-flex", alignItems: "center", gap: 8,
                    background: "var(--primary-light)", border: "1px solid var(--primary-soft)",
                    borderRadius: 20, padding: "5px 14px 5px 10px",
                  }}>
                    <PictureOutlined style={{ color: "var(--primary)", fontSize: 13 }} />
                    <Text style={{ fontSize: 12, color: "var(--text)" }}>{imageFile.name}</Text>
                    <Button type="text" size="small" icon={<DeleteOutlined />}
                      onClick={() => setImageFile(null)}
                      style={{ color: "var(--text-muted)", minWidth: 20 }} />
                  </div>
                )}
                {videoFile && (
                  <div style={{
                    display: "inline-flex", alignItems: "center", gap: 8,
                    background: "#fef3c7", border: "1px solid #fcd34d",
                    borderRadius: 20, padding: "5px 14px 5px 10px",
                  }}>
                    <VideoCameraOutlined style={{ color: "#d97706", fontSize: 13 }} />
                    <Text style={{ fontSize: 12, color: "var(--text)" }}>{videoFile.name}</Text>
                    <Button type="text" size="small" icon={<DeleteOutlined />}
                      onClick={() => setVideoFile(null)}
                      style={{ color: "var(--text-muted)", minWidth: 20 }} />
                  </div>
                )}
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

              {/* 视频上传按钮 */}
              <Upload
                accept="video/*"
                maxCount={1}
                showUploadList={false}
                beforeUpload={(file) => { handleVideoUpload(file); return false; }}
              >
                <Button type="text" icon={<VideoCameraOutlined />}
                  style={{ color: videoFile ? "#d97706" : "var(--text-muted)", fontSize: 18, width: 40, height: 40 }} />
              </Upload>

              {/* 视频生成按钮 */}
              <Popover
                open={genPopOpen}
                onOpenChange={setGenPopOpen}
                trigger="click"
                placement="topRight"
                title="AI 视频生成"
                content={
                  <div style={{ width: 320 }}>
                    <Input.TextArea
                      rows={3} value={genPrompt} onChange={e => setGenPrompt(e.target.value)}
                      placeholder="描述你想生成的视频..."
                      style={{ marginBottom: 10 }}
                    />
                    <Space wrap style={{ marginBottom: 10 }}>
                      <Select value={genRatio} onChange={setGenRatio} style={{ width: 80 }} size="small"
                        options={[{value:"16:9",label:"16:9"},{value:"9:16",label:"9:16"},{value:"1:1",label:"1:1"}]} />
                      <Select value={genDuration} onChange={setGenDuration} style={{ width: 70 }} size="small"
                        options={[5,10,15].map(d=>({value:d,label:`${d}秒`}))} />
                    </Space>
                    <Button type="primary" block icon={<ThunderboltOutlined />}
                      onClick={handleVideoGenerate} loading={generatingVideo}>
                      生成视频
                    </Button>
                  </div>
                }
              >
                <Button type="text" icon={<ThunderboltOutlined />}
                  style={{ color: generatingVideo ? "var(--primary)" : "var(--text-muted)", fontSize: 18, width: 40, height: 40 }} />
              </Popover>

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
