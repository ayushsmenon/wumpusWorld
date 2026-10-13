
import os
from bisect import bisect_right
from pathlib import Path

from ingestion.models import (CorruptFileError, EmptyFileError, ParsedUnit,
                              UnsupportedFormatError)

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")
TARGET_SECONDS = 45
MAX_SECONDS = 90

EXTRACT_FRAMES = os.environ.get("EXTRACT_FRAMES", "1") != "0"
FRAME_INTERVAL = 30

FRAME_CHANGE_THRESHOLD = 10
MAX_FRAMES = 150

_model = None


def _load_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise UnsupportedFormatError(
                "faster-whisper is not installed. Run: pip install faster-whisper") from e
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def format_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def group_segments(raw: list) -> list:
    """raw = [{'start','end','text'}, ...] -> merged groups of the same shape."""
    groups, cur = [], []

    def flush():
        if cur:
            groups.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                           "text": " ".join(s["text"] for s in cur)})
            cur.clear()

    for seg in raw:
        if cur and seg["end"] - cur[0]["start"] > MAX_SECONDS:
            flush()
        cur.append(seg)
        if seg["end"] - cur[0]["start"] >= TARGET_SECONDS:
            flush()
    flush()
    return groups


def _signature(img):
    return list(img.convert("L").resize((32, 32)).getdata())


def extract_frames(path: Path, out_dir: Path, duration: float) -> list:
    frames = []
    try:
        import av
    except ImportError:
        return frames
    try:
        with av.open(str(path)) as container:
            if not container.streams.video:
                return frames
            stream = container.streams.video[0]
            out_dir.mkdir(parents=True, exist_ok=True)
            prev, t = None, 0.0
            while t < max(duration, 1) and len(frames) < MAX_FRAMES:
                try:
                    container.seek(int(t / stream.time_base), stream=stream)
                    frame = next(container.decode(stream), None)
                    if frame is None:
                        break
                    img = frame.to_image()
                    sig = _signature(img)
                    brightness = sum(sig) / len(sig)
                    changed = prev is None or \
                        sum(abs(a - b) for a, b in zip(sig, prev)) / \
                        len(sig) > FRAME_CHANGE_THRESHOLD
                    if brightness > 8 and changed:
                        img.thumbnail((1280, 1280))
                        name = f"frame_{int(t):06d}.jpg"
                        img.save(out_dir / name, quality=85)
                        frames.append({"kind": "video_frame", "path": f"{out_dir.name}/{name}",
                                       "bbox": None, "width": img.width, "height": img.height,
                                       "time_sec": round(t, 2)})
                        prev = sig
                except Exception:
                    pass
                t += FRAME_INTERVAL
    except Exception:
        pass
    return frames


def attach_frames(units: list, frames: list):
    if not units or not frames:
        return
    starts = [u.start_sec for u in units]
    for fr in frames:
        idx = max(0, bisect_right(starts, fr["time_sec"]) - 1)
        units[idx].images.append(fr)
        units[idx].has_visuals = True


def parse_video(path: Path, out_dir: Path) -> list:
    model = _load_model()
    try:
        segments, info = model.transcribe(
            str(path), vad_filter=True, beam_size=5)
        raw = [{"start": s.start, "end": s.end, "text": s.text.strip()}
               for s in segments if s.text.strip()]
    except Exception as e:
        raise CorruptFileError(
            f"Could not transcribe file: {type(e).__name__}: {e}") from e

    if not raw:
        raise EmptyFileError("No speech found in the file")

    units = []
    for i, g in enumerate(group_segments(raw), start=1):
        units.append(ParsedUnit(
            "segment", i, g["text"],
            start_sec=round(g["start"], 2), end_sec=round(g["end"], 2),
            metadata={"timestamp": format_ts(g["start"]),
                      "language": info.language,
                      "language_probability": round(info.language_probability, 3),
                      "whisper_model": MODEL_SIZE},
        ))

    if EXTRACT_FRAMES:
        attach_frames(units, extract_frames(path, out_dir, info.duration))
    return units
