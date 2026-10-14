from pathlib import Path

from ingestion.models import CorruptFileError, ParsedUnit


def parse_image(path: Path, out_dir: Path) -> list:
    from PIL import Image
    try:
        img = Image.open(path)
        original_format = img.format
        img.load()
        img = img.convert("RGB")
    except Exception as e:
        raise CorruptFileError(f"Could not open image: {e}") from e

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "image_0001.png"
    img.save(dest)
    image = {"kind": "picture", "path": f"{out_dir.name}/{dest.name}", "bbox": None,
             "width": img.width, "height": img.height}
    return [ParsedUnit("image", 1, "", images=[image], has_visuals=True,
                       metadata={"original_format": original_format})]
