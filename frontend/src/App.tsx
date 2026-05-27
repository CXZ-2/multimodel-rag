import { Routes, Route, Navigate } from "react-router-dom";
import UploadPage from "./pages/Upload";
import ChatPage from "./pages/Chat";
import KnowledgeBase from "./pages/KnowledgeBase";
import ImageSearchPage from "./pages/ImageSearch";

export default function App() {
  return (
    <Routes>
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/knowledge" element={<KnowledgeBase />} />
      <Route path="/image-search" element={<ImageSearchPage />} />
      <Route path="*" element={<Navigate to="/upload" replace />} />
    </Routes>
  );
}
