from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from models import Point, Region


class TemplateMatcherError(RuntimeError):
    pass


@dataclass(frozen=True)
class TemplateMatch:
    name: str
    found: bool
    confidence: float
    center: Point | None = None
    top_left: Point | None = None
    template_size: tuple[int, int] | None = None
    template_path: Path | None = None


def _import_cv2_numpy():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise TemplateMatcherError("Instale as dependencias com: pip install -r requirements.txt") from exc
    return cv2, np


def image_to_gray_array(image):
    cv2, np = _import_cv2_numpy()
    if isinstance(image, (str, Path)):
        array = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
        if array is None:
            raise TemplateMatcherError(f"Nao foi possivel ler imagem: {image}")
        return array

    if hasattr(image, "convert"):
        return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)

    array = np.asarray(image)
    if array.ndim == 2:
        return array
    if array.ndim == 3:
        return cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    raise TemplateMatcherError("Formato de imagem nao suportado.")


def match_template(image, template, name: str = "", threshold: float = 0.85, template_path: Path | None = None) -> TemplateMatch:
    cv2, _np = _import_cv2_numpy()
    haystack = image_to_gray_array(image)
    needle = image_to_gray_array(template)
    template_height, template_width = needle.shape[:2]
    image_height, image_width = haystack.shape[:2]

    if template_width > image_width or template_height > image_height:
        return TemplateMatch(
            name=name,
            found=False,
            confidence=0.0,
            template_size=(template_width, template_height),
            template_path=template_path,
        )

    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    _min_value, max_value, _min_location, max_location = cv2.minMaxLoc(result)
    confidence = float(max_value)
    top_left = Point(x=int(max_location[0]), y=int(max_location[1]))
    center = Point(
        x=top_left.x + template_width // 2,
        y=top_left.y + template_height // 2,
    )
    return TemplateMatch(
        name=name,
        found=confidence >= threshold,
        confidence=confidence,
        center=center,
        top_left=top_left,
        template_size=(template_width, template_height),
        template_path=template_path,
    )


def find_best_template(image, templates: Iterable[tuple[str, Path]], threshold: float = 0.85) -> TemplateMatch:
    best: TemplateMatch | None = None
    for name, path in templates:
        if not path.exists():
            continue
        match = match_template(image, path, name=name, threshold=threshold, template_path=path)
        if best is None or match.confidence > best.confidence:
            best = match
    if best is None:
        return TemplateMatch(name="", found=False, confidence=0.0)
    if best.confidence < threshold:
        return TemplateMatch(
            name=best.name,
            found=False,
            confidence=best.confidence,
            center=best.center,
            top_left=best.top_left,
            template_size=best.template_size,
            template_path=best.template_path,
        )
    return best


def draw_match_box(image, match: TemplateMatch, output_path: Path, offset: Region | None = None) -> Path:
    if not match.top_left or not match.template_size:
        raise TemplateMatcherError("Match sem coordenadas para desenhar debug.")
    cv2, np = _import_cv2_numpy()
    if hasattr(image, "convert"):
        array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    else:
        array = np.asarray(image).copy()
        if array.ndim == 2:
            array = cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
    left = match.top_left.x
    top = match.top_left.y
    width, height = match.template_size
    cv2.rectangle(array, (left, top), (left + width, top + height), (0, 0, 255), 2)
    label = f"{match.name}:{match.confidence:.3f}"
    cv2.putText(array, label, (left, max(12, top - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), array)
    return output_path
