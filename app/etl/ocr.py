"""可选 OCR 引擎：依赖缺失或关闭时降级为 None。"""

from __future__ import annotations

from loguru import logger

from app.etl.parser import OcrEngine


class TesseractOcrEngine:
    """pytesseract + pdf2image 实现；需系统安装 tesseract 与 poppler。"""

    def __init__(self, lang: str = "chi_sim+eng", dpi: int = 200) -> None:
        self._lang = lang
        self._dpi = dpi

    def extract_text(self, pdf_bytes: bytes) -> str:
        import pytesseract
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(pdf_bytes, dpi=self._dpi)
        parts = [
            pytesseract.image_to_string(image, lang=self._lang) for image in images
        ]
        return "\n".join(parts)


def build_ocr_engine(enabled: bool) -> OcrEngine | None:
    """按开关构造 OCR 引擎；依赖缺失时降级为 None，不影响上传。"""
    if not enabled:
        return None
    try:
        import pdf2image  # noqa: F401
        import pytesseract  # noqa: F401
    except ImportError:
        logger.warning("OCR 已开启但缺少 pytesseract/pdf2image，已降级为不启用")
        return None
    return TesseractOcrEngine()
