"""
rapidocr/
├─ __init__.py
├─ engine.py           # ctypes RapidOcrEngine
├─ worker.py           # internal worker
├─ async_engine.py     # NEW: thread + worker wrapper (main interface)
├─ bin/
└─ models/
"""

from .rapidocr_engine import RapidOcrEngine
from .async_engine import OcrService

__all__ = ["RapidOcrEngine", "OcrEngine"]
