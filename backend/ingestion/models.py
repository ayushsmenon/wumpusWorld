from dataclasses import dataclass, field
from typing import Optional

PARSED = "parsed"
EMPTY = "empty"
PASSWORD_PROTECTED = "password_protected"
UNSUPPORTED = "unsupported"
CORRUPT = "corrupt"


class IngestionError(Exception):
    status = CORRUPT


class EmptyFileError(IngestionError):
    status = EMPTY


class PasswordProtectedError(IngestionError):
    status = PASSWORD_PROTECTED


class UnsupportedFormatError(IngestionError):
    status = UNSUPPORTED


class CorruptFileError(IngestionError):
    status = CORRUPT


@dataclass
class ParsedUnit:
    unit_type: str                      # "page" | "slide" | "segment"
    number: int
    text: str = ""
    tables: list = field(default_factory=list)
    images: list = field(default_factory=list)
    has_visuals: bool = False
    needs_ocr: bool = False
    notes: str = ""
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    metadata: dict = field(default_factory=dict)


UNIT_PREFIX = {"page": "p", "slide": "s", "segment": "t", "image": "i"}


def make_source_id(file_id: str, unit_type: str, number: int) -> str:
    return f"{file_id}:{UNIT_PREFIX.get(unit_type, 'u')}{number}"
