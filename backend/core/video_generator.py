"""视频生成 — 多通道 T2V（DashScope 万相 / OpenAI Sora）"""
import httpx
from backend.config import settings

DASHSCOPE_API = "https://dashscope.aliyuncs.com/api/v1"
API_KEY = settings.DASHSCOPE_API_KEY


def generate_wanxiang(prompt: str, resolution: str = "720P",
                      ratio: str = "16:9", duration: int = 5,
                      negative_prompt: str = None) -> str:
    """通义万相文生视频 — 创建任务，返回 task_id"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    body = {
        "model": settings.T2V_MODEL,
        "input": {"prompt": prompt},
        "parameters": {
            "resolution": resolution,
            "ratio": ratio,
            "duration": duration,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    if negative_prompt:
        body["input"]["negative_prompt"] = negative_prompt

    resp = httpx.post(
        f"{DASHSCOPE_API}/services/aigc/video-generation/video-synthesis",
        headers=headers,
        json=body,
        timeout=30,
    )

    if resp.status_code == 200:
        data = resp.json()
        return data["output"]["task_id"]
    else:
        raise Exception(f"万相视频生成失败 (code={resp.status_code}): {resp.text}")


def generate_sora(prompt: str, resolution: str = "720P",
                  duration: int = 5) -> str:
    """OpenAI Sora 文生视频 — 创建任务，返回 task_id"""
    from openai import OpenAI

    client = OpenAI()
    raise NotImplementedError("Sora API 尚未正式发布，请使用万相通道")


def generate_video(prompt: str, model: str = "wanx2.1-t2v-turbo",
                   resolution: str = "720P", ratio: str = "16:9",
                   duration: int = 5, negative_prompt: str = None) -> str:
    """统一 T2V 入口，根据 model 参数路由到不同通道，返回 task_id"""
    if model in ("wanx2.1-t2v-turbo", "wanx"):
        return generate_wanxiang(prompt, resolution, ratio, duration, negative_prompt)
    elif model == "sora":
        return generate_sora(prompt, resolution, duration)
    else:
        raise ValueError(f"不支持的模型: {model}")


def query_wanxiang_task(task_id: str) -> dict:
    """查询万相任务状态"""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    resp = httpx.get(
        f"{DASHSCOPE_API}/tasks/{task_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        return {
            "task_id": task_id,
            "status": data["output"]["task_status"],
            "video_url": data["output"].get("video_url"),
        }
    else:
        raise Exception(f"查询任务失败 (code={resp.status_code}): {resp.text}")


def query_task(task_id: str, model: str = "wanx2.1-t2v-turbo") -> dict:
    """统一查询任务状态入口"""
    if model in ("wanx2.1-t2v-turbo", "wanx"):
        return query_wanxiang_task(task_id)
    else:
        raise ValueError(f"不支持的模型: {model}")
