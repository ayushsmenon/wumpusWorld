"""
runs on any unit that has images: PDF pages, slides, standalone image files,
video frames, converted Word/ODT pages. 
"""
import argparse
import os
import sys
import time

from ingestion import registry

MODEL_NAME = os.environ.get(
    "VISION_MODEL", "HuggingFaceTB/SmolVLM-500M-Instruct")
MAX_NEW_TOKENS = 350
MAX_IMAGES_PER_UNIT = 4
NO_VISUAL = "NO VISUAL CONTENT"

PROMPTS = {
    "figure": ("Look at this page. Ignore ordinary paragraphs of text. For every figure, "
               "diagram, chart, graph, table drawn as an image, equation, or photo on it: "
               "say what kind it is, read out all labels, numbers, axis names and symbols "
               "exactly, and explain in one or two sentences what it shows. If there is no "
               f"such visual content, reply exactly: {NO_VISUAL}"),
    "ocr": ("Transcribe all the text on this page exactly as written, in reading order. "
            "Then briefly describe any figures or diagrams on it."),
    "general": ("Describe this image. If it contains text, transcribe it exactly. If it is a "
                "diagram, chart, graph, table, equation or code, say which and read out all "
                "labels, numbers and relationships exactly."),
}

_model = _processor = _device = None


def _load():
    global _model, _processor, _device
    if _model is None:
        import torch
        from transformers import AutoProcessor
        try:
            from transformers import AutoModelForImageTextToText as AutoModel
        except ImportError:
            from transformers import AutoModelForVision2Seq as AutoModel
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if _device == "cuda" else torch.float32
        _processor = AutoProcessor.from_pretrained(MODEL_NAME)
        _model = AutoModel.from_pretrained(
            MODEL_NAME, torch_dtype=dtype).to(_device)
        _model.eval()
    return _model, _processor, _device


def describe_image(image, mode: str = "figure") -> str:
    import torch
    from PIL import Image
    model, processor, device = _load()
    if not isinstance(image, Image.Image):
        image = Image.open(image)
    image = image.convert("RGB")
    messages = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": PROMPTS[mode]}]}]
    prompt = processor.apply_chat_template(
        messages, add_generation_prompt=True)
    inputs = processor(text=prompt, images=[
                       image], return_tensors="pt").to(device)
    inputs["pixel_values"] = inputs["pixel_values"].to(model.dtype)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                             repetition_penalty=1.1)
    new_tokens = out[:, inputs["input_ids"].shape[1]:]
    return processor.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()


def pick_targets(unit: dict) -> list:
    images = unit["images"]
    renders = [im for im in images if im.get(
        "kind") == "page_render" and im.get("path")]
    if renders:
        return renders[:1]
    return [im for im in images if im.get("path")][:MAX_IMAGES_PER_UNIT]


def mode_for(unit: dict) -> str:
    if unit["needs_ocr"]:
        return "ocr"
    if unit["unit_type"] in ("image", "segment"):
        return "general"
    return "figure"


def _stamp(image: dict, caption: str) -> str:
    if image.get("time_sec") is not None:
        s = int(image["time_sec"])
        return f"[{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}] {caption}"
    return caption


def caption_file(conn, file_id: str, force: bool = False, log=print) -> dict:
    stats = {"units": 0, "images": 0, "failed": 0, "no_image": 0}
    todo = []
    for u in registry.get_units(conn, file_id):
        if not (u["has_visuals"] or u["needs_ocr"] or u["unit_type"] == "image"):
            continue
        targets = pick_targets(u)
        if not targets:
            stats["no_image"] += 1
            continue
        pending = [t for t in targets if force or "caption" not in t]
        if pending:
            todo.append((u, targets, pending))

    for n, (u, targets, pending) in enumerate(todo, start=1):
        mode = mode_for(u)
        log(f"  [vision {n}/{len(todo)}] {u['unit_type']} {u['number']} "
            f"({len(pending)} image{'s' if len(pending) != 1 else ''}, {mode})")
        started = time.time()
        for t in pending:
            try:
                text = describe_image(registry.EXTRACTED_DIR / t["path"], mode)
            except ImportError:
                raise
            except Exception as e:
                t["caption_error"] = f"{type(e).__name__}: {e}"
                stats["failed"] += 1
                continue
            t.pop("caption_error", None)
            t["caption"] = "" if text.upper().startswith(NO_VISUAL) else text
            stats["images"] += 1

        captions = [_stamp(t, t["caption"])
                    for t in targets if t.get("caption")]
        if mode == "ocr":
            new_text = "\n".join(captions)
            registry.set_vision_result(
                conn, u["source_id"], "", u["images"],
                text=(new_text if new_text and not u["text"] else None),
                metadata={"text_from_vision": bool(new_text and not u["text"]),
                          "vision_model": MODEL_NAME})
            if new_text and u["text"]:
                registry.set_vision_result(conn, u["source_id"], new_text, u["images"],
                                           metadata={"vision_model": MODEL_NAME})
        else:
            registry.set_vision_result(conn, u["source_id"], "\n".join(captions), u["images"],
                                       metadata={"vision_model": MODEL_NAME})
        stats["units"] += 1
        log(f"      done in {time.time() - started:.0f}s")
    return stats


def main():
    ap = argparse.ArgumentParser(
        description="Describe images in ingested files.")
    ap.add_argument("--course", required=True)
    ap.add_argument("--force", action="store_true",
                    help="redo images that already have captions")
    args = ap.parse_args()
    conn = registry.connect()
    files = [f for f in registry.list_files(
        conn, args.course) if f["status"] == "parsed"]
    if not files:
        print("No parsed files for that course.")
        sys.exit(1)
    for f in files:
        print(f["filename"])
        try:
            print("  ", caption_file(conn, f["file_id"], force=args.force))
        except ImportError as e:
            print(
                f"Vision libraries missing ({e}). Run: pip install torch transformers pillow accelerate num2words")
            sys.exit(1)


if __name__ == "__main__":
    main()
