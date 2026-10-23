import re
from itertools import chain

from PyQt6.QtWidgets import QApplication

from dataclasses import dataclass, field


@dataclass
class ExtractedItems:
    coach_nr: list[str] = field(default_factory=list)
    coach_moid: list[str] = field(default_factory=list)
    material_12NC: list[str] = field(default_factory=list)
    service_order: list[str] = field(default_factory=list)
    error_code: list[str] = field(default_factory=list)
    machine_nr: list[str] = field(default_factory=list)
    air_id: list[str] = field(default_factory=list)


def unique(items: list[str]) -> list:
    return list(dict.fromkeys(items))


ALPHA_TABLE = str.maketrans({"1": "l", "0": "O", "8": "B"})
NUM_TABLE = str.maketrans({"O": "0", "l": "1", "I": "1", "o": "0"})
VALID_NUM_CHARS = set("0123456789OlIo")  #  O(1)

# Compile once at module level, not every time OCR runs.
COACH_NR_RE = re.compile(
    r"(?<![A-Za-z0-9.])[a-z]+[a-z0-9]*\.[a-z]{3}(?![A-Za-z0-9.])",
    re.IGNORECASE,
)

# Begin and end cannot be any text, number or comma
COACH_MOID_RE = re.compile(r"(?<![A-Za-z0-9.])\d{5,}(?![A-Za-z0-9.])")

NC_12_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:\d{4}|[a-z]{4})\.\d{3}\.\d{4,5}" r"(?![A-Za-z0-9.])",
    re.IGNORECASE,
)

SO_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:SO|S0)?\d{8}(?![A-Za-z0-9])",
    re.IGNORECASE,
)

ERROR_RE = re.compile(
    r"(?<![A-Za-z0-9])[a-z]{2}-[a-z0-9]{4}(?![A-Za-z0-9])",
    re.IGNORECASE,
)

MACHINE_NR_RE = re.compile(
    r"(?<![A-Za-z0-9.])"  # cannot begin with any text, number or comma
    r"m?"  # can has M nor not
    r"((?:[A-Za-z]{2}|\d{2})\d{2})"  # exact 2 letters or 2 digits.
    r"(?![A-Za-z0-9.])",  # cannot end with any text, number or comma
    re.IGNORECASE,
)


AIR_RE = re.compile(r"(?<![A-Za-z0-9])P\d{5,}(?![A-Za-z0-9])", re.IGNORECASE)


def preprocess_ocr_text(text: str) -> str:
    # Letter -> digit when surrounded by digits
    text = re.sub(r"(?<=\d)?=\d", "0", text)
    text = re.sub(r"(?<=\d)?=\d", "1", text)
    text = re.sub(r"(?<=\d)?=\d", "5", text)
    text = re.sub(r"(?<=\d)?=\d", "8", text)

    # Digit -> letter when surrounded by letters
    text = re.sub(r"(?<=[A-Za-z])0(?=[A-Za-z])", "O", text)
    text = re.sub(r"(?<=[A-Za-z])1(?=[A-Za-z])", "I", text)
    text = re.sub(r"(?<=[A-Za-z])5(?=[A-Za-z])", "S", text)
    text = re.sub(r"(?<=[A-Za-z])8(?=[A-Za-z])", "B", text)

    # O at the end of a numeric sequence: 5359654O -> 53596540
    text = re.sub(r"(?<=\d)[Oo]\b", "0", text)

    # SO: S/O confusion at beginning, e.g. S053596540 -> SO53596540
    # Only S + 0 followed by digits
    text = re.sub(r"\b[Ss]0(?=\d)", "SO", text)

    return text


def correct_procedure_format(text: str) -> str:
    """
    correct procedure from ocr text
    """
    if len(text) < 3:
        return text
    prefix = text[0:3].translate(ALPHA_TABLE)
    idx = 3
    text_len = len(text)
    while idx < text_len and text[idx] in VALID_NUM_CHARS:
        idx += 1
    middle = text[3:idx].translate(NUM_TABLE)
    suffix = text[idx:]
    return prefix + middle + suffix


def extract_search_items(text: str):
    """
    Extract search items from input text.
    """
    # Coach numbers need additional formatting.
    coach_list = [
        correct_procedure_format(value) for value in COACH_NR_RE.findall(text)
    ]

    coach_moid_list = COACH_MOID_RE.findall(text)
    nc_12_list = NC_12_RE.findall(text)
    so_list = SO_RE.findall(text)
    error_list = ERROR_RE.findall(text)
    machine_nr = MACHINE_NR_RE.findall(text)
    air_id = AIR_RE.findall(text)

    # Merge and remove duplicates while preserving original order.
    unique_list = list(
        dict.fromkeys(
            chain(
                coach_list,
                coach_moid_list,
                so_list,
                nc_12_list,
                error_list,
                machine_nr,
                air_id,
            )
        )
    )
    return unique_list


def extract_items(text: str) -> ExtractedItems:
    return ExtractedItems(
        coach_nr=unique(COACH_NR_RE.findall(text)),
        coach_moid=unique(COACH_MOID_RE.findall(text)),
        material_12NC=unique(NC_12_RE.findall(text)),
        service_order=unique(SO_RE.findall(text)),
        error_code=unique(ERROR_RE.findall(text)),
        machine_nr=unique(MACHINE_NR_RE.findall(text)),
        air_id=unique(AIR_RE.findall(text)),
    )
