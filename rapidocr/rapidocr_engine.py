import os
import ctypes
import tempfile
import threading
import uuid
from pathlib import Path
from PyQt6.QtCore import Qt


class OCR_PARAM(ctypes.Structure):
    _fields_ = [
        ("padding", ctypes.c_int),
        ("maxSideLen", ctypes.c_int),
        ("boxScoreThresh", ctypes.c_float),
        ("boxThresh", ctypes.c_float),
        ("unClipRatio", ctypes.c_float),
        ("doAngle", ctypes.c_int),
        ("mostAngle", ctypes.c_int),
    ]


class RapidOcrEngine:
    """
    RapidOcrOnnx ctypes wrapper.

    This wrapper supports DLLs exposing only:

        OcrInit
        OcrDetect
        OcrGetLen
        OcrGetResult
        OcrDestroy

    Since OcrDetectInput is not exported by your DLL,
    pixmap/QImage input must be saved to an image file first.
    """

    def __init__(
        self,
        dll_path=None,
        det_model=None,
        cls_model=None,
        rec_model=None,
        key_file=None,
        threads=1,
        padding=50,
        max_side_len=1024,
        box_score_thresh=0.3,
        box_thresh=0.3,
        unclip_ratio=1.6,
        do_angle=1,
        most_angle=1,
        temp_dir=None,
        debug=False,
    ):
        self.debug = bool(debug)
        self.threads = int(threads)
        self.handle = None
        self.dll = None
        self._lock = threading.Lock()

        self.package_dir = Path(__file__).resolve().parent
        self.bin_dir = self.package_dir / "bin"
        self.models_dir = self.package_dir / "models"

        self.dll_path = (
            Path(dll_path).resolve() if dll_path else self.bin_dir / "RapidOcrOnnx.dll"
        )

        self.det_model = (
            Path(det_model).resolve()
            if det_model
            else self.models_dir / "ch_PP-OCRv4_det_infer.onnx"
        )
        self.cls_model = (
            Path(cls_model).resolve()
            if cls_model
            else self.models_dir / "ch_ppocr_mobile_v2.0_cls_infer.onnx"
        )
        self.rec_model = (
            Path(rec_model).resolve()
            if rec_model
            else self.models_dir / "ch_PP-OCRv4_rec_infer.onnx"
        )
        self.key_file = (
            Path(key_file).resolve()
            if key_file
            else self.models_dir / "ppocr_keys_v1.txt"
        )

        if temp_dir is None:
            self.temp_dir = Path(tempfile.gettempdir())
        else:
            self.temp_dir = Path(temp_dir).resolve()

        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.default_param = OCR_PARAM(
            padding=int(padding),
            maxSideLen=int(max_side_len),
            boxScoreThresh=float(box_score_thresh),
            boxThresh=float(box_thresh),
            unClipRatio=float(unclip_ratio),
            doAngle=int(do_angle),
            mostAngle=int(most_angle),
        )

        self._check_files()
        self._load_dll()
        self._bind_functions()
        self._init_engine()

    def _log(self, *args):
        if self.debug:
            print("[RapidOcrEngine]", *args)

    def _check_files(self):
        required_files = {
            "DLL": self.dll_path,
            "DET_MODEL": self.det_model,
            "CLS_MODEL": self.cls_model,
            "REC_MODEL": self.rec_model,
            "KEY_FILE": self.key_file,
        }

        for name, path in required_files.items():
            if not path.exists():
                raise FileNotFoundError(f"{name} not found: {path}")

    @staticmethod
    def _encode_path(path):
        return str(Path(path).resolve()).encode("utf-8")

    def _load_dll(self):
        """
        Add bin folder to DLL search path, then load main RapidOCR DLL.
        """
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(self.bin_dir))
            os.add_dll_directory(str(self.dll_path.parent))

        self._log("Loading DLL:", self.dll_path)
        self.dll = ctypes.CDLL(str(self.dll_path))

    def _bind_functions(self):
        self.dll.OcrInit.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        self.dll.OcrInit.restype = ctypes.c_void_p

        self.dll.OcrDetect.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.POINTER(OCR_PARAM),
        ]
        self.dll.OcrDetect.restype = ctypes.c_int

        self.dll.OcrGetLen.argtypes = [
            ctypes.c_void_p,
        ]
        self.dll.OcrGetLen.restype = ctypes.c_int

        self.dll.OcrGetResult.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_char),
            ctypes.c_int,
        ]
        self.dll.OcrGetResult.restype = ctypes.c_int

        self.dll.OcrDestroy.argtypes = [
            ctypes.c_void_p,
        ]
        self.dll.OcrDestroy.restype = None

    def _init_engine(self):
        self._log("Initializing OCR engine")

        self.handle = self.dll.OcrInit(
            self._encode_path(self.det_model),
            self._encode_path(self.cls_model),
            self._encode_path(self.rec_model),
            self._encode_path(self.key_file),
            self.threads,
        )

        if not self.handle:
            raise RuntimeError(
                "OcrInit failed. Check DLL dependencies, model files, key file, and Python/DLL bitness."
            )

        self._log("OcrInit handle:", self.handle)

    def close(self):
        with self._lock:
            if self.handle:
                self._log("Destroying OCR handle")
                self.dll.OcrDestroy(self.handle)
                self.handle = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _get_img_dir_and_name(self, image_file):
        """
        Your DLL appears to internally concatenate:

            imgPath + imgName

        Therefore imgPath must end with '\\' on Windows.
        """
        image_file = Path(image_file).resolve()
        img_dir = str(image_file.parent)

        if os.name == "nt":
            if not img_dir.endswith("\\"):
                img_dir += "\\"
        else:
            if not img_dir.endswith("/"):
                img_dir += "/"

        img_name = image_file.name

        return img_dir, img_name

    def recognize_image_file(self, image_file, param=None):
        """
        Recognize text from an image path.

        Parameters
        ----------
        image_file:
            Path to image file.

        Returns
        -------
        str
            OCR result text.
        """
        image_file = Path(image_file).resolve()

        if not image_file.exists():
            raise FileNotFoundError(f"Image file not found: {image_file}")

        if param is None:
            param = self.default_param

        img_dir, img_name = self._get_img_dir_and_name(image_file)

        self._log("img_dir :", img_dir)
        self._log("img_name:", img_name)
        self._log("exists  :", os.path.exists(img_dir + img_name))

        with self._lock:
            if not self.handle:
                raise RuntimeError("OCR engine is already closed.")

            detect_ret = self.dll.OcrDetect(
                self.handle,
                img_dir.encode("utf-8"),
                img_name.encode("utf-8"),
                ctypes.byref(param),
            )

            self._log("OcrDetect:", detect_ret)

            if detect_ret != 1:
                raise RuntimeError(
                    f"OcrDetect failed. ret={detect_ret}, image={image_file}"
                )

            result_len = self.dll.OcrGetLen(self.handle)

            self._log("OcrGetLen:", result_len)

            if result_len <= 0:
                return ""

            # Your DLL behavior:
            #   OcrGetLen = text bytes + null terminator
            #   OcrGetResult = text bytes written
            buf_size = result_len + 16
            buf = ctypes.create_string_buffer(buf_size)

            result_ret = self.dll.OcrGetResult(
                self.handle,
                buf,
                buf_size,
            )

            self._log("OcrGetResult:", result_ret)

            if result_ret <= 0:
                raise RuntimeError(
                    f"OcrGetResult failed. ret={result_ret}, OcrGetLen={result_len}"
                )

            raw = buf.raw.split(b"\x00", 1)[0]
            text = raw.decode("utf-8", errors="replace")

            return text

    def recognize_pixmap(
        self, pixmap, suffix=".png", remove_temp=True, scale: float = 1.0
    ):
        """
        Recognize text from PyQt6 QPixmap.

        Since your DLL has no OcrDetectInput, the pixmap is saved to a temporary
        PNG first, then OcrDetect reads that image file.

        Parameters
        ----------
        pixmap:
            PyQt6.QtGui.QPixmap

        suffix:
            Usually ".png".

        remove_temp:
            Delete temp image after OCR.

        Returns
        -------
        str
            OCR result text.
        """
        if pixmap is None:
            raise ValueError("pixmap is None")
        # Resize the image that OCR will read, not just its on-screen display.
        if hasattr(pixmap, "isNull") and pixmap.isNull():
            raise ValueError("pixmap is null")
        if scale > 1:
            ocr_pixmap = pixmap.scaled(
                round(pixmap.width() * scale),
                round(pixmap.height() * scale),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # print(ocr_pixmap.size())
        else:
            ocr_pixmap = pixmap

        temp_name = f"rapidocr_{uuid.uuid4().hex}{suffix}"
        temp_path = self.temp_dir / temp_name

        ok = ocr_pixmap.save(str(temp_path), "PNG")

        if not ok:
            raise RuntimeError(f"Failed to save pixmap to temp file: {temp_path}")

        self._log("Saved pixmap:", temp_path)

        try:
            return self.recognize_image_file(temp_path)
        finally:
            if remove_temp:
                try:
                    temp_path.unlink()
                    self._log("Removed temp file:", temp_path)
                except OSError:
                    pass

    def recognize_qimage(self, qimage, suffix=".png", remove_temp=True):
        """
        Recognize text from PyQt6 QImage.
        """
        if qimage is None:
            raise ValueError("qimage is None")

        if hasattr(qimage, "isNull") and qimage.isNull():
            raise ValueError("qimage is null")

        temp_name = f"rapidocr_{uuid.uuid4().hex}{suffix}"
        temp_path = self.temp_dir / temp_name

        ok = qimage.save(str(temp_path), "PNG")
        if not ok:
            raise RuntimeError(f"Failed to save qimage to temp file: {temp_path}")

        self._log("Saved qimage:", temp_path)

        try:
            return self.recognize_image_file(temp_path)
        finally:
            if remove_temp:
                try:
                    temp_path.unlink()
                    self._log("Removed temp file:", temp_path)
                except OSError:
                    pass

    # # Optional aliases, in case you prefer shorter names.
    # detect_image_file = recognize_image_file
    # detect_pixmap = recognize_pixmap
    # detect_qimage = recognize_qimage


# if __name__ == "__main__":
#     import sys

#     from PyQt6.QtWidgets import QApplication
#     from PyQt6.QtGui import QPixmap
#     import time

#     app = QApplication(sys.argv)

#     image_path = r"C:\Users\agieng\Desktop\failed_image.png"

#     pixmap = QPixmap(image_path)

#     engine = RapidOcrEngine(debug=False)

#     try:
#         start_time = time.perf_counter()
#         text = engine.recognize_pixmap(pixmap, scale=1, remove_temp=True)
#         # text = engine.recognize_image_file(image_path)
#         print("OCR RESULT:")
#         print(text)
#         print(f"time: {(time.perf_counter()-start_time)*1000:2f}ms")
#     finally:
#         engine.close()
