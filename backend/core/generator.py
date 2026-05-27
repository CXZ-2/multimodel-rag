import dashscope
from dashscope import Generation, MultiModalConversation
from backend.config import settings

dashscope.api_key = settings.DASHSCOPE_API_KEY


def _build_vl_content(image_base64: str) -> tuple[str, list[dict]]:
    """构建 VL 多模态消息格式，返回 (model, content)"""
    if image_base64.startswith("http://") or image_base64.startswith("https://") or image_base64.startswith("file://"):
        image_url = image_base64
    else:
        image_url = f"data:image/png;base64,{image_base64}"
    content = [
        {"image": image_url},
        {"text": ""},
    ]
    return settings.DASHSCOPE_VL_MODEL, content


def _extract_vl_text(response) -> str:
    """从 MultiModalConversation 响应中提取文本"""
    content = response.output.choices[0].message.content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if "text" in p)
    return content


def _call_llm(prompt: str, image_base64: str = None) -> str:
    """调用通义千问（同步），有图片时自动切换 VL 模型"""
    if image_base64:
        model, content = _build_vl_content(image_base64)
        content[-1]["text"] = prompt
        response = MultiModalConversation.call(
            model=model,
            messages=[{"role": "user", "content": content}],
        )
        if response.status_code == 200:
            return _extract_vl_text(response)
        else:
            raise Exception(f"通义千问 VL 调用失败 (code={response.status_code}): {response.message}")
    else:
        response = Generation.call(
            model=settings.DASHSCOPE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
        )
        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise Exception(f"通义千问调用失败 (code={response.status_code}): {response.message}")


def _call_llm_stream(prompt: str, image_base64: str = None):
    """流式调用通义千问，有图片时返回 VL 完整结果，无图片时逐 token 流式"""
    if image_base64:
        # VL 模型流式支持有限，先取完整结果再 yield
        answer = _call_llm(prompt, image_base64=image_base64)
        yield answer
    else:
        response = Generation.call(
            model=settings.DASHSCOPE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            stream=True,
            incremental_output=True,
        )
        for event in response:
            if event.status_code == 200 and event.output:
                token = event.output.choices[0].message.content
                if token:
                    yield token
