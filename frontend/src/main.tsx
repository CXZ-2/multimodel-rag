import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#5e81fe",
          colorPrimaryBg: "#eff3ff",
          colorPrimaryBgHover: "#dbe4ff",
          colorPrimaryBorder: "#b8caff",
          colorPrimaryHover: "#4a6ef5",
          colorPrimaryActive: "#3b5de6",
          colorSuccess: "#10b981",
          colorWarning: "#f59e0b",
          colorError: "#ef4444",
          colorInfo: "#5e81fe",
          colorTextBase: "#1a1d23",
          colorTextSecondary: "#6b7280",
          colorBgBase: "#ffffff",
          colorBgContainer: "#ffffff",
          colorBgElevated: "#ffffff",
          colorBgLayout: "#f9fafb",
          colorBorder: "#e5e7eb",
          colorBorderSecondary: "#f3f4f6",
          borderRadius: 10,
          borderRadiusLG: 14,
          borderRadiusSM: 8,
          fontFamily: "'Geist', -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: 14,
          fontSizeLG: 16,
          fontSizeXL: 20,
          controlHeight: 38,
          controlHeightLG: 46,
          paddingLG: 20,
          paddingMD: 16,
          boxShadow: "0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04)",
          boxShadowSecondary: "0 4px 6px rgba(0,0,0,.04), 0 2px 4px rgba(0,0,0,.04)",
        },
        components: {
          Card: {
            paddingLG: 24,
            borderRadiusLG: 14,
          },
          Button: {
            primaryShadow: "0 1px 2px rgba(94,129,254,.2)",
            fontWeight: 500,
          },
          Descriptions: {
            itemPaddingBottom: 12,
            labelBg: "transparent",
          },
          Tag: {
            borderRadiusSM: 6,
          },
        },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
);
