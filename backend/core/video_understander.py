"""视频理解 — 使用 DashScope Qwen-VL 原生 API 理解视频内容"""
import httpx
import json
import base64
import os
from backend.config import settings

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = settings.DASHSCOPE_API_KEY

UNDERSTAND_PROMPT = """请全面分析这个视频，用中文回复，按以下结构输出 JSON：

{
  "summary": "视频整体内容概述（100-200字）",
  "scenes": [{"timestamp": "开始时间", "description": "场景描述"}],
  "events": [{"timestamp": "时间", "action": "动作/事件描述"}],
  "objects": ["视频中出现的物体/人物列表"],
  "ocr_text": "视频中出现的所有文字内容",
  "style": "视频风格（纪实/动画/教程/演讲等）",
  "tags": ["标签1", "标签2"]
}

只输出 JSON，不要其他内容。"""


def understand_video(video_path: str) -> dict:
    """调用 DashScope Qwen-VL 理解视频内容，返回结构化 JSON"""
    with open(video_path, "rb") as f:
        video_base64 = base64.b64encode(f.read()).decode()

    ext = os.path.splitext(video_path)[1].lower()
    mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime",
                ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
                ".webm": "video/webm"}
    mime_type = mime_map.get(ext, "video/mp4")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [{"role": "user", "content": [
        {"type": "video_url",
         "video_url": {"url": f"data:{mime_type};base64,{video_base64}"}},
        {"type": "text", "text": UNDERSTAND_PROMPT},
    ]}]

    body = {
        "model": settings.VIDEO_UNDERSTAND_MODEL,
        "messages": messages,
    }

    resp = httpx.post(
        f"{DASHSCOPE_BASE}/chat/completions",
        headers=headers,
        json=body,
        timeout=300
    )

    if resp.status_code == 200:
        content = resp.json()["choices"][0]["message"]["content"]
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                if content.endswith("```"):
                    content = content[:-3]
            return json.loads(content)
        except json.JSONDecodeError:
            return {"summary": content, "raw": True}
    else:
        raise Exception(f"视频理解失败 (code={resp.status_code}): {resp.text}")


def transcribe_audio(audio_path: str) -> str:
    """使用 faster-whisper 将音频转为文字"""
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, language="zh")
    text = " ".join(seg.text for seg in segments)
    return text
