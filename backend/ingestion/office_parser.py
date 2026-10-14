import subprocess
import tempfile
from pathlib import Path

from ingestion.models import CorruptFileError, UnsupportedFormatError
from ingestion.pdf_parser import parse_pdf
from ingestion.slide_parser import LIBREOFFICE_TIMEOUT, find_soffice


def parse_office(path: Path, out_dir: Path) -> list:
    soffice = find_soffice()
    if not soffice:
        raise UnsupportedFormatError(
            f"Reading '{path.suffix}' files needs LibreOffice installed (it converts the "
            "file to PDF first). Install it, or export the file to PDF yourself.")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(path)],
                           check=True, timeout=LIBREOFFICE_TIMEOUT, capture_output=True)
        except Exception as e:
            raise CorruptFileError(
                f"LibreOffice could not convert the file: {e}") from e
        pdfs = list(Path(tmp).glob("*.pdf"))
        if not pdfs:
            raise CorruptFileError("LibreOffice produced no PDF")
        units = parse_pdf(pdfs[0], out_dir)
    for u in units:
        u.metadata["converted_via"] = "libreoffice"
    return units
