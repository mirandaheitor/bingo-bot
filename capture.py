from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from PIL import Image

from models import PlayerCalibration, Region


class CaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapturedImage:
    image: Image.Image
    region: Region


def _import_mss():
    try:
        import mss
    except ImportError as exc:
        raise CaptureError("Instale as dependencias com: pip install -r requirements.txt") from exc
    return mss


def capture_virtual_screen() -> CapturedImage:
    mss = _import_mss()
    with mss.mss() as screenshotter:
        monitor = screenshotter.monitors[0]
        shot = screenshotter.grab(monitor)
    image = Image.frombytes("RGB", shot.size, shot.rgb)
    region = Region(
        x=int(monitor["left"]),
        y=int(monitor["top"]),
        width=int(monitor["width"]),
        height=int(monitor["height"]),
    )
    return CapturedImage(image=image, region=region)


def capture_region(region: Region) -> CapturedImage:
    if region.width <= 0 or region.height <= 0:
        raise CaptureError(f"Regiao invalida para captura: {region}")
    mss = _import_mss()
    monitor = {
        "left": region.x,
        "top": region.y,
        "width": region.width,
        "height": region.height,
    }
    with mss.mss() as screenshotter:
        shot = screenshotter.grab(monitor)
    image = Image.frombytes("RGB", shot.size, shot.rgb)
    return CapturedImage(image=image, region=region)


def calibrated_regions(calibration: PlayerCalibration) -> Mapping[str, Region]:
    return {
        "window": calibration.window_region,
        "grid": calibration.grid_region,
        "setup_number": calibration.setup_number_region,
        "setup_text": calibration.setup_text_region,
        "turn": calibration.turn_region,
        "result": calibration.result_region,
    }


def save_region_capture(region: Region, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    captured = capture_region(region)
    captured.image.save(path)
    return path


def capture_calibration(calibration: PlayerCalibration, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for name, region in calibrated_regions(calibration).items():
        saved.append(save_region_capture(region, output_dir / f"{name}.png"))
    return saved
