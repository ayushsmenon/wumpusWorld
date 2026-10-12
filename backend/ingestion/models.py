
from dataclasses import dataclass, field


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

    unit_type: str
    number: int
    text: str = ""

    tables: list = field(default_factory=list)

    images: list = field(default_factory=list)

    has_visuals: bool = False

    needs_ocr: bool = False
