import { useState, useEffect } from "react";
import { Modal, Select, InputNumber, Alert, message } from "antd";
import { crawlDocuments, getCrawlSources, type CrawlSource } from "../services/api";

interface CrawlModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function CrawlModal({ open, onClose, onSuccess }: CrawlModalProps) {
  const [crawling, setCrawling] = useState(false);
  const [crawlSources, setCrawlSources] = useState<Record<string, CrawlSource>>({});
  const [crawlSource, setCrawlSource] = useState("gov_zhengce");
  const [crawlLimit, setCrawlLimit] = useState(10);

  useEffect(() => {
    if (open) {
      getCrawlSources()
        .then(setCrawlSources)
        .catch(() => { /* use defaults */ });
    }
  }, [open]);

  const handleCrawl = async () => {
    setCrawling(true);
    try {
      const res = await crawlDocuments({ source: crawlSource, limit: crawlLimit });
      message.success(`爬取完成: 新增 ${res.crawled} 篇, 跳过 ${res.skipped} 篇`);
      onClose();
      onSuccess?.();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "爬取失败");
    } finally {
      setCrawling(false);
    }
  };

  return (
    <Modal
      title="网页爬取"
      open={open}
      onCancel={onClose}
      onOk={handleCrawl}
      confirmLoading={crawling}
      okText="开始爬取"
      cancelText="取消"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 8 }}>
        <div>
          <div style={{ marginBottom: 6, fontWeight: 500 }}>数据源</div>
          <Select
            value={crawlSource}
            onChange={setCrawlSource}
            style={{ width: "100%" }}
            options={Object.entries(crawlSources).map(([key, s]) => ({
              value: key,
              label: `${s.name} — ${s.base_url}`,
            }))}
          />
        </div>
        <div>
          <div style={{ marginBottom: 6, fontWeight: 500 }}>每源爬取篇数</div>
          <InputNumber min={1} max={50} value={crawlLimit} onChange={(v) => setCrawlLimit(v ?? 10)} style={{ width: "100%" }} />
        </div>
        <Alert
          type="info"
          message="爬取后文档将自动清洗、向量化并存入知识库。"
          style={{ fontSize: 12 }}
        />
      </div>
    </Modal>
  );
}
