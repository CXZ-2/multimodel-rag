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


def embed_texts_batch(texts: list[str]) -> list[list[float]]:
    """批量文本编码，减少模型前向推理次数"""
    if not texts:
        return []
    model, processor = get_model()
    all_embeddings = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        inputs = processor(text=batch, return_tensors="pt", padding=True)
        with torch.no_grad():
            features = model.get_text_features(**inputs)
        features = features / features.norm(dim=-1, keepdim=True)
        all_embeddings.extend(features.tolist())
    return all_embeddings


def embed_images_batch(image_paths: list[str]) -> list[list[float]]:
    """批量图片编码"""
    if not image_paths:
        return []
    model, processor = get_model()
    images = [Image.open(p).convert("RGB") for p in image_paths]
    all_embeddings = []
    batch_size = 16
    for i in range(0, len(images), batch_size):
        batch = images[i:i + batch_size]
        inputs = processor(images=batch, return_tensors="pt")
        with torch.no_grad():
            features = model.get_image_features(**inputs)
        features = features / features.norm(dim=-1, keepdim=True)
        all_embeddings.extend(features.tolist())
    return all_embeddings
