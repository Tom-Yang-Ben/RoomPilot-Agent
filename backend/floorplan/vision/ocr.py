"""可選的 PaddleOCR adapter；核心管線可用測試或人工 observations 取代。"""

from __future__ import annotations

from typing import Any

import numpy as np

from .image import decode_image


class PaddleOCRProvider:
    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        self._engine = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize(self, image_bytes: bytes) -> list[dict[str, Any]]:
        image = decode_image(image_bytes)
        try:
            result = self._engine.predict(input=image)
        except AttributeError:
            result = self._engine.ocr(image, cls=True)
        return _normalise_paddle_result(result)


def _bbox(points: Any) -> list[float] | None:
    array = np.asarray(points, dtype=float)
    if array.ndim < 2 or array.shape[-1] != 2:
        return None
    return [
        float(array[:, 0].min()),
        float(array[:, 1].min()),
        float(array[:, 0].max()),
        float(array[:, 1].max()),
    ]


def _normalise_paddle_result(result: Any) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for item in result or []:
        raw = getattr(item, "json", item)
        raw = raw() if callable(raw) else raw
        if isinstance(raw, dict):
            payload = raw.get("res", raw)
            texts = payload.get("rec_texts", [])
            scores = payload.get("rec_scores", [])
            polygons = payload.get("dt_polys", payload.get("rec_polys", []))
            for text, score, polygon in zip(texts, scores, polygons):
                box = _bbox(polygon)
                if box:
                    observations.append({"text": str(text), "bbox": box, "confidence": float(score)})
            continue
        rows = item if isinstance(item, list) else []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                continue
            box = _bbox(row[0])
            text_score = row[1]
            if box and isinstance(text_score, (list, tuple)) and len(text_score) == 2:
                observations.append({"text": str(text_score[0]), "bbox": box, "confidence": float(text_score[1])})
    return observations


def default_ocr_provider() -> PaddleOCRProvider | None:
    try:
        return PaddleOCRProvider()
    except (ImportError, ModuleNotFoundError):
        return None
