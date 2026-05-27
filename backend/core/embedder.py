import torch
from PIL import Image
from transformers import ChineseCLIPModel, ChineseCLIPProcessor
from backend.config import settings

_model = None
_processor = None


def get_model():
    global _model, _processor
    if _model is None:
        _model = ChineseCLIPModel.from_pretrained(settings.CLIP_MODEL_NAME)
        _processor = ChineseCLIPProcessor.from_pretrained(settings.CLIP_MODEL_NAME)
    return _model, _processor


def embed_text(text: str) -> list[float]:
    """文本编码为向量"""
    model, processor = get_model()
    inputs = processor(text=[text], return_tensors="pt", padding=True)
    with torch.no_grad():
        features = model.get_text_features(**inputs)
    features = features / features.norm(dim=-1, keepdim=True)
    return features[0].tolist()


def _embed_image_pil(image: Image.Image) -> list[float]:
    """PIL Image 编码为向量"""
    model, processor = get_model()
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
    features = features / features.norm(dim=-1, keepdim=True)
    return features[0].tolist()


def embed_image(image_path: str) -> list[float]:
    """图片路径 → 向量"""
    image = Image.open(image_path).convert("RGB")
    return _embed_image_pil(image)


def embed_image_base64(image_base64: str) -> list[float]:
    """Base64 → 图片向量"""
    import base64
    from io import BytesIO
    img_bytes = base64.b64decode(image_base64)
    image = Image.open(BytesIO(img_bytes)).convert("RGB")
    return _embed_image_pil(image)
