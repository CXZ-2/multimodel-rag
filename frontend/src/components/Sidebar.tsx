import { useNavigate, useLocation } from "react-router-dom";
import { NAV_ITEMS } from "../constants";

interface SidebarProps {
  statusText?: string;
}

export default function Sidebar({ statusText = "Milvus 已连接" }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <aside className="app-sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">O</div>
        <div>
          <span className="sidebar-logo-text">OmniMind</span>
          <span className="sidebar-logo-sub">多模态智能知识平台</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <div
            key={item.path}
            className={`sidebar-nav-item ${location.pathname === item.path ? "active" : ""}`}
            onClick={() => navigate(item.path)}
          >
            {item.icon}
            {item.label}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="sidebar-status">
          <div className="sidebar-status-dot" />
          系统运行中 · {statusText}
        </div>
      </div>
    </aside>
  );
}
