from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from calibrate import calibration_to_file_data, load_calibration, recalibrate_continue_button, select_region
from capture import CaptureError, calibrated_regions, capture_calibration, capture_region
from models import PlayerSide
from result_detector import detect_result_for_player
from setup_number_detector import detect_setup_number_for_player
from setup_state_detector import detect_setup_state_for_player
from turn_detector import detect_turn_for_player


DEBUG_DIR = Path("debug")
ASSETS_DIR = Path("assets")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run_capture_diagnostic(side: PlayerSide) -> Path:
    calibration = load_calibration(side)
    output_dir = DEBUG_DIR / f"diagnostic_{side.value}_{_timestamp()}"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "side": side.value,
        "name": calibration.name,
        "output_dir": str(output_dir),
        "calibration": calibration_to_file_data(calibration),
        "absolute_regions": {name: asdict(region) for name, region in calibrated_regions(calibration).items()},
        "captures": [],
    }

    try:
        paths = capture_calibration(calibration, output_dir)
    except CaptureError as exc:
        summary["error"] = str(exc)
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        raise

    summary["captures"] = [str(path) for path in paths]
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Diagnostico salvo em: {output_dir}")
    for path in paths:
        print(f"- {path}")
    return output_dir


def create_templates_menu() -> None:
    while True:
        print(
            """===== TEMPLATES BINGO =====

1 - Capturar numero de preparacao
2 - Capturar texto MY_TURN
3 - Capturar texto WAITING
4 - Capturar texto READY
5 - Capturar YOU WIN da instancia
6 - Capturar YOU LOSE da instancia
7 - Capturar DRAW da instancia
8 - Testar detectores esquerda
9 - Testar detectores direita
10 - Recalibrar Continue/OK da tela final
11 - Voltar
"""
        )
        option = input("Escolha uma opcao: ").strip()
        if option == "1":
            _capture_setup_number_template()
        elif option == "2":
            _capture_turn_template("my_turn.png", "Selecione somente o texto/estado que indica seu turno")
        elif option == "3":
            _capture_turn_template("waiting.png", "Selecione somente o texto/estado que indica aguardando o oponente")
        elif option == "4":
            _capture_ready_template()
        elif option == "5":
            _capture_result_template("you_win.png", "Selecione somente o texto/imagem YOU WIN")
        elif option == "6":
            _capture_result_template("you_lose.png", "Selecione somente o texto/imagem YOU LOSE")
        elif option == "7":
            _capture_result_template("draw.png", "Selecione somente o texto/estado DRAW")
        elif option == "8":
            run_detection_diagnostic(PlayerSide.LEFT)
        elif option == "9":
            run_detection_diagnostic(PlayerSide.RIGHT)
        elif option == "10":
            recalibrate_continue_button(_prompt_side())
        elif option == "11":
            return
        else:
            print("Opcao invalida.")


def test_setup_number(side: PlayerSide) -> None:
    calibration = load_calibration(side)
    output_dir = DEBUG_DIR / f"setup_number_test_{side.value}_{_timestamp()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    detection = detect_setup_number_for_player(calibration, output_dir)
    if detection.found:
        print(f"Numero detectado: {detection.number} | confianca={detection.confidence:.3f}")
    else:
        print(f"Numero UNKNOWN | melhor confianca={detection.confidence:.3f}")
    print(f"Debug salvo em: {output_dir}")


def run_detection_diagnostic(side: PlayerSide) -> Path:
    calibration = load_calibration(side)
    output_dir = DEBUG_DIR / f"detection_{side.value}_{_timestamp()}"
    output_dir.mkdir(parents=True, exist_ok=True)

    setup_number = detect_setup_number_for_player(calibration, output_dir)
    setup_state = detect_setup_state_for_player(calibration, output_dir)
    turn = detect_turn_for_player(calibration, output_dir)
    result = detect_result_for_player(calibration, output_dir)

    summary = {
        "side": side.value,
        "setup_number": {
            "found": setup_number.found,
            "number": setup_number.number,
            "confidence": setup_number.confidence,
            "template": str(setup_number.match.template_path) if setup_number.match.template_path else None,
        },
        "setup_state": setup_state.value,
        "turn": turn.value,
        "result": result.value,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Diagnostico de deteccao salvo em: {output_dir}")
    print(f"Numero preparacao: {setup_number.number if setup_number.found else 'UNKNOWN'} ({setup_number.confidence:.3f})")
    print(f"Estado setup: {setup_state.value}")
    print(f"Turno: {turn.value}")
    print(f"Resultado: {result.value}")
    return output_dir


def _capture_setup_number_template() -> Path:
    number = _prompt_number()
    side = _prompt_side()
    calibration = load_calibration(side)
    input(f"Deixe o numero {number} visivel na preparacao dessa instancia e pressione Enter...")
    captured = capture_region(calibration.setup_number_region)
    return _save_template_from_capture(
        captured,
        ASSETS_DIR / "setup_numbers" / f"{number}.png",
        f"Selecione exatamente o numero {number}",
    )


def _capture_turn_template(filename: str, title: str) -> Path:
    side = _prompt_side()
    calibration = load_calibration(side)
    input("Deixe esse estado visivel nessa instancia e pressione Enter...")
    captured = capture_region(calibration.turn_region)
    return _save_template_from_capture(captured, ASSETS_DIR / "states" / filename, title)


def _capture_ready_template() -> Path:
    side = _prompt_side()
    calibration = load_calibration(side)
    input("Deixe o estado Ready/aguardando inicio visivel nessa instancia e pressione Enter...")
    captured = capture_region(calibration.setup_text_region)
    return _save_template_from_capture(
        captured,
        ASSETS_DIR / "states" / "ready.png",
        "Selecione somente o texto/estado READY",
    )


def _capture_result_template(filename: str, title: str) -> Path:
    side = _prompt_side()
    calibration = load_calibration(side)
    input("Deixe a tela de resultado visivel nessa instancia e pressione Enter...")
    captured = capture_region(calibration.result_region)
    return _save_template_from_capture(captured, ASSETS_DIR / "states" / filename, title)


def _save_template_from_capture(captured: CapturedImage, output_path: Path, title: str) -> Path:
    region = select_region(captured, title)
    crop = captured.image.crop((region.x, region.y, region.x + region.width, region.y + region.height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(output_path)
    print(f"Template salvo em: {output_path} ({crop.width}x{crop.height})")
    return output_path


def _prompt_side() -> PlayerSide:
    while True:
        value = input("Instancia para captura [e]squerda/[d]ireita: ").strip().lower()
        if value in {"e", "esquerda", "left", "l"}:
            return PlayerSide.LEFT
        if value in {"d", "direita", "right", "r"}:
            return PlayerSide.RIGHT
        print("Informe e ou d.")


def _prompt_number() -> int:
    while True:
        value = input("Numero de preparacao para capturar [1-25]: ").strip()
        if value.isdigit() and 1 <= int(value) <= 25:
            return int(value)
        print("Informe um numero de 1 a 25.")
