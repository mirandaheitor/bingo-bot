from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import time

from battle_runtime import BattleDryRunRuntime
from board_builder import simulate_setup_for_side
from bot_runner import BotRunError, BotRuntime
from calibrate import CalibrationError, run_calibration
import config
from diagnostics import create_templates_menu, run_capture_diagnostic, test_setup_number
from hotkeys import BotCancelledError, is_escape_pressed, raise_if_escape_pressed
from input_controller import InputController, RealClickDisabledError
from game_controller import GameController, empty_observation
from models import PlayerSide
from window_message_input import WindowMessageError, message_click_at_point, post_click_absolute


MENU = """===== BINGO BOT =====

1 - Calibrar esquerda
2 - Calibrar direita
3 - Criar/atualizar templates
4 - Diagnostico esquerda
5 - Diagnostico direita
6 - Testar numero de preparacao
7 - Testar Undo/Confirm/Continue
8 - Simular montagem em dry-run
9 - Simular batalha em dry-run
10 - Rodar 1 partida
11 - Rodar N partidas
12 - Rodar infinito
13 - Sair
14 - Testar envio de mensagem sem mover mouse
"""


def simulate_state_machine() -> None:
    controller = GameController(winner_side=PlayerSide.LEFT)
    print(controller.start())
    for _index in range(4):
        print(controller.step(empty_observation()))


def simulate_live_battle() -> None:
    winner_side = _prompt_side("Qual lado deve vencer? [e]squerda/[d]ireita: ")
    max_cycles = _prompt_int("Quantidade maxima de ciclos dry-run [padrao 10]: ", default=10)
    runtime = BattleDryRunRuntime.from_calibrations(winner_side)
    debug_dir = Path("debug") / f"battle_dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    debug_dir.mkdir(parents=True, exist_ok=True)
    print(f"Vencedor configurado: {winner_side.value}")
    print(f"Debug: {debug_dir}")
    print("Como nao ha clique real nesta etapa, avance a tela manualmente entre os ciclos quando houver acao planejada.")
    for index in range(1, max_cycles + 1):
        cycle = runtime.observe_and_step(debug_dir)
        print()
        print(f"Ciclo {index}")
        print(cycle.describe())
        if cycle.command.action.value in {"continue_both", "blocked"}:
            break
        next_step = input("Enter para novo ciclo, q para voltar: ").strip().lower()
        if next_step == "q":
            break


def simulate_board_setup() -> None:
    winner_side = _prompt_side("Qual lado deve vencer? [e]squerda/[d]ireita: ")
    side = _prompt_side("Qual instancia simular? [e]squerda/[d]ireita: ")
    print(f"Vencedor configurado: {winner_side.value}")
    print(f"Instancia simulada: {side.value}")
    commands = simulate_setup_for_side(side=side, winner_side=winner_side)
    for index, command in enumerate(commands, start=1):
        print(f"{index:02d}. DRY-RUN {command.describe()}")


def test_real_buttons() -> None:
    if not _confirm_real_clicks("TESTAR BOTOES"):
        return
    side = _prompt_side("Qual instancia testar? [e]squerda/[d]ireita: ")
    from calibrate import load_calibration

    calibration = load_calibration(side)
    controller = InputController(dry_run=False, real_clicks_enabled=True, cancel_checker=is_escape_pressed)
    _countdown(config.DELAY_BEFORE_START)
    controller.click_point(calibration.undo_button, f"{side.value} Undo", focus=calibration)
    _sleep_cancelable(config.DELAY_AFTER_UNDO)
    controller.click_point(calibration.confirm_button, f"{side.value} Confirm/Continue", focus=calibration)
    print("Teste de botoes concluido.")


def test_window_message_click() -> None:
    print("ATENCAO: teste experimental. Nao move o mouse real, mas pode clicar no jogo.")
    value = input("Digite exatamente 'TESTAR MENSAGEM' para continuar: ").strip()
    if value not in {"TESTAR MENSAGEM", "TESTAR POSTMESSAGE"}:
        print("Operacao cancelada.")
        return
    side = _prompt_side("Qual instancia testar? [e]squerda/[d]ireita: ")
    print(
        """Alvo:
1 - Confirm
2 - Continue/OK
3 - Undo
4 - Clear
"""
    )
    target = input("Escolha o alvo: ").strip()
    print(
        """Metodo:
1 - PostMessage na janela calibrada
2 - PostMessage no hwnd sob o ponto alvo
3 - SendMessage no hwnd sob o ponto alvo
4 - PostMessage hover+click no hwnd sob o ponto alvo
5 - SendMessage hover+click no hwnd sob o ponto alvo
"""
    )
    method_option = input("Escolha o metodo: ").strip()
    from calibrate import load_calibration

    calibration = load_calibration(side)
    if target == "1":
        point = calibration.confirm_button
        label = "Confirm"
    elif target == "2":
        point = calibration.continue_button
        label = "Continue/OK"
    elif target == "3":
        point = calibration.undo_button
        label = "Undo"
    elif target == "4":
        point = calibration.clear_button
        label = "Clear"
    else:
        print("Alvo invalido.")
        return
    if method_option == "1":
        result = post_click_absolute(calibration, point, button="left")
    elif method_option == "2":
        result = message_click_at_point(point, button="left", method="post_child")
    elif method_option == "3":
        result = message_click_at_point(point, button="left", method="send_child")
    elif method_option == "4":
        result = message_click_at_point(point, button="left", method="post_hover_child")
    elif method_option == "5":
        result = message_click_at_point(point, button="left", method="send_hover_child")
    else:
        print("Metodo invalido.")
        return
    print(
        f"{result.method} enviado para {label}. "
        f"hwnd={result.target.hwnd} title='{result.target.title}' "
        f"client=({result.client_point.x},{result.client_point.y})"
    )


def run_one_real_match() -> None:
    if not _confirm_real_clicks("RODAR UMA PARTIDA"):
        return
    winner_side = _prompt_side("Qual lado deve vencer? [e]squerda/[d]ireita: ")
    max_cycles = _prompt_int("Quantidade maxima de ciclos por fase [padrao 80]: ", default=80)
    _run_real_matches(winner_side=winner_side, match_count=1, max_cycles=max_cycles)


def run_n_real_matches() -> None:
    if not _confirm_real_clicks("RODAR N PARTIDAS"):
        return
    winner_side = _prompt_side("Qual lado deve vencer? [e]squerda/[d]ireita: ")
    match_count = _prompt_int("Quantidade de partidas: ", default=1)
    max_cycles = _prompt_int("Quantidade maxima de ciclos por fase [padrao 80]: ", default=80)
    _run_real_matches(winner_side=winner_side, match_count=match_count, max_cycles=max_cycles)


def run_infinite_real_matches() -> None:
    if not _confirm_real_clicks("RODAR LOOP INFINITO"):
        return
    winner_side = _prompt_side("Qual lado deve vencer? [e]squerda/[d]ireita: ")
    max_cycles = _prompt_int("Quantidade maxima de ciclos por fase [padrao 80]: ", default=80)
    _run_real_matches(winner_side=winner_side, match_count=None, max_cycles=max_cycles)


def _run_real_matches(winner_side: PlayerSide, match_count: int | None, max_cycles: int) -> None:
    _countdown(config.DELAY_BEFORE_START)
    match_index = 1
    while match_count is None or match_index <= match_count:
        raise_if_escape_pressed()
        total = "loop" if match_count is None else str(match_count)
        print()
        print(f"===== PARTIDA {match_index}/{total} =====")
        runtime = BotRuntime(
            winner_side=winner_side,
            dry_run=False,
            real_clicks_enabled=True,
            input_controller=InputController(dry_run=False, real_clicks_enabled=True, cancel_checker=is_escape_pressed),
        )
        debug_dir = Path("debug") / f"real_match_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{match_index}"
        result = runtime.run_match(max_cycles=max_cycles, debug_root=debug_dir)
        print(f"Resultado runtime: completed={result.completed} ciclos={result.cycles} | {result.reason}")
        if not result.completed:
            return
        match_index += 1
        if match_count is None or match_index <= match_count:
            _sleep_cancelable(config.DELAY_AFTER_CONTINUE)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        print(MENU)
        option = input("Escolha uma opcao: ").strip()
        try:
            if option == "1":
                run_calibration(PlayerSide.LEFT)
            elif option == "2":
                run_calibration(PlayerSide.RIGHT)
            elif option == "3":
                create_templates_menu()
            elif option == "4":
                run_capture_diagnostic(PlayerSide.LEFT)
            elif option == "5":
                run_capture_diagnostic(PlayerSide.RIGHT)
            elif option == "6":
                side = _prompt_side("Qual instancia testar? [e]squerda/[d]ireita: ")
                test_setup_number(side)
            elif option == "7":
                test_real_buttons()
            elif option == "8":
                simulate_board_setup()
            elif option == "9":
                simulate_live_battle()
            elif option == "10":
                run_one_real_match()
            elif option == "11":
                run_n_real_matches()
            elif option == "12":
                run_infinite_real_matches()
            elif option == "13":
                break
            elif option == "14":
                test_window_message_click()
            else:
                print("Opcao reservada para etapa posterior.")
        except CalibrationError as exc:
            print(f"Erro de calibracao: {exc}")
        except KeyboardInterrupt:
            print("Interrompido por Ctrl+C.")
        except (BotCancelledError, BotRunError, RealClickDisabledError, WindowMessageError) as exc:
            print(str(exc))
        except Exception as exc:
            logging.exception("Falha inesperada")
            print(f"Erro: {exc}")


def _prompt_side(prompt: str) -> PlayerSide:
    while True:
        value = input(prompt).strip().lower()
        if value in {"e", "esquerda", "left", "l"}:
            return PlayerSide.LEFT
        if value in {"d", "direita", "right", "r"}:
            return PlayerSide.RIGHT
        print("Informe e ou d.")


def _prompt_int(prompt: str, default: int) -> int:
    value = input(prompt).strip()
    if not value:
        return default
    return int(value)


def _confirm_real_clicks(expected: str) -> bool:
    print("ATENCAO: esta opcao pode clicar de verdade nas janelas calibradas.")
    print("Deixe o mouse livre. Use ESC ou Ctrl+C para interromper se necessario.")
    value = input(f"Digite exatamente '{expected}' para continuar: ").strip()
    if value != expected:
        print("Operacao cancelada.")
        return False
    return True


def _countdown(seconds: float) -> None:
    total = max(1, int(seconds))
    for remaining in range(total, 0, -1):
        raise_if_escape_pressed()
        print(f"Iniciando em {remaining}...")
        _sleep_cancelable(1.0)


def _sleep_cancelable(seconds: float) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        raise_if_escape_pressed()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.05, remaining))


if __name__ == "__main__":
    main()
