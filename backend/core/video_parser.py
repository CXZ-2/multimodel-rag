"""视频文件解析 — 关键帧提取 + 音频提取"""
import os
import av
import subprocess
from backend.config import settings


def extract_key_frames(video_path: str, max_frames: int = None) -> list[str]:
    """从视频中提取关键帧，返回图片路径列表"""
    if max_frames is None:
        max_frames = settings.VIDEO_KEY_FRAMES

    frame_paths = []
    os.makedirs(settings.FRAMES_DIR, exist_ok=True)

    container = av.open(video_path)
    video_stream = container.streams.video[0]
    duration = float(video_stream.duration * video_stream.time_base) if video_stream.duration else 0

    if duration == 0:
        container.close()
        return frame_paths

    # 均匀采样 max_frames 个时间点
    interval = duration / (max_frames + 1)
    target_ts = [interval * (i + 1) for i in range(max_frames)]

    frame_idx = 0
    for ts in target_ts:
        container.seek(int(ts * 1000000), stream=video_stream)
        for frame in container.decode(video=0):
            img = frame.to_image()
            frame_name = f"{os.path.basename(video_path)}_frame_{frame_idx:03d}.jpg"
            frame_path = os.path.join(settings.FRAMES_DIR, frame_name)
            img.save(frame_path)
            frame_paths.append(frame_path)
            frame_idx += 1
            break  # 只取第一个解码帧

    container.close()
    return frame_paths


def get_video_metadata(video_path: str) -> dict:
    """获取视频元数据"""
    container = av.open(video_path)
    video_stream = container.streams.video[0]
    audio_stream = container.streams.audio[0] if container.streams.audio else None

    duration = float(video_stream.duration * video_stream.time_base) if video_stream.duration else 0
    metadata = {
        "duration": round(duration, 1),
        "resolution": f"{video_stream.width}x{video_stream.height}",
        "fps": round(float(video_stream.average_rate), 1),
        "codec": video_stream.codec_context.name,
        "has_audio": audio_stream is not None,
    }
    container.close()
    return metadata


def extract_audio(video_path: str) -> str:
    """从视频中提取音频为 16kHz mono WAV，返回音频文件路径"""
    audio_dir = os.path.join(settings.UPLOAD_DIR, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, f"{os.path.basename(video_path)}.wav")

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return audio_path
