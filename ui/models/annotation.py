from dataclasses import dataclass

from .tools import Tool

ANNOTATION_ITEM = 1
ANNOTATION_DATA = 1
EDITABLE_ITEM = 2


@dataclass(slots=True, frozen=True)
class AnnotationData:
    tool: Tool | None
    editable: bool = True
