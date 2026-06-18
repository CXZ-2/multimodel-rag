import httpx
import json as _json
from backend.config import settings

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = settings.DASHSCOPE_API_KEY


def _call_llm(prompt: str, image_base64: str = None) -> str:
    """调用通义千问（OpenAI 兼容模式），有图片时自动切换 VL 模型"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    if image_base64:
        model = settings.DASHSCOPE_VL_MODEL
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
            {"type": "text", "text": prompt},
        ]}]
    else:
        model = settings.DASHSCOPE_MODEL
        messages = [{"role": "user", "content": prompt}]

    body = {"model": model, "messages": messages}
    resp = httpx.post(f"{DASHSCOPE_BASE}/chat/completions", headers=headers, json=body, timeout=60)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"通义千问调用失败 (code={resp.status_code}): {resp.text}")


def _call_llm_stream(prompt: str, image_base64: str = None):
    """流式调用通义千问"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    if image_base64:
        model = settings.DASHSCOPE_VL_MODEL
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
            {"type": "text", "text": prompt},
        ]}]
    else:
        model = settings.DASHSCOPE_MODEL
        messages = [{"role": "user", "content": prompt}]

    body = {"model": model, "messages": messages, "stream": True}
    with httpx.stream("POST", f"{DASHSCOPE_BASE}/chat/completions", headers=headers, json=body, timeout=120) as resp:
        if resp.status_code != 200:
            yield f"调用失败 (code={resp.status_code})"
            return
        for line in resp.iter_lines():
            if line.startswith("data:"):
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = _json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token
                except Exception:
                    continue
