"""Command-line entrypoint for the single hardware-backed game interface."""

from __future__ import annotations

import argparse
import sys
import time
import traceback

import pygame

from pqc_sat.infrastructure.serial_client import WisdomSerialClient
from pqc_sat.settings import FPS, SERIAL_TIMEOUT_SECONDS
from pqc_sat.stand.investigation import InvestigationController
from pqc_sat.stand.model import StandConfig
from pqc_sat.stand.session import StandSessionLogger
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH, DEFAULT_LOG_DIR
from pqc_sat.ui.display import DISPLAY, init_display
from pqc_sat.ui.game import GamePanel
from pqc_sat.ui.scene import CosmicDust, Nebula, ShootingStars, StarField
from pqc_sat.ui.theme import C_SPACE_BG
from tools.serial_bridge import SerialBridgeError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PQC-SAT — jogo por etapas com BlackBoard Wisdom obrigatória",
    )
    parser.add_argument("--port", help="porta serial da Wisdom; se omitida, todas as portas são sondadas")
    parser.add_argument("--baud", type=int, default=115200, help="baudrate da serial")
    parser.add_argument(
        "--probe-timeout",
        type=float,
        default=2.5,
        help="timeout de cada HELLO usado para descobrir a placa",
    )
    parser.add_argument(
        "--serial-timeout",
        type=float,
        default=SERIAL_TIMEOUT_SECONDS,
        help="timeout dos comandos GAME_* em segundos",
    )
    parser.add_argument("--windowed", action="store_true", help="abre em janela em vez de tela cheia")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="configuração JSON do jogo")
    parser.add_argument("--log-dir", type=str, default=str(DEFAULT_LOG_DIR), help="diretório dos logs JSONL")
    parser.add_argument("--diagnostic", action="store_true", help="mostra o painel administrativo F12")
    parser.add_argument(
        "--no-splash",
        action="store_true",
        help="omite apenas o standby visual; a Wisdom continua obrigatória",
    )
    parser.add_argument(
        "--restart-on-crash",
        action="store_true",
        help="reinicia o processo do jogo após erro inesperado; não contorna ausência da placa",
    )
    parser.add_argument("--max-runtime-seconds", type=float, help=argparse.SUPPRESS)
    return parser


def parse_args(argv=None):
    return build_parser().parse_args(argv)


def build_game_runtime(args, port: str | None = None, *, config: StandConfig | None = None):
    """Compose the game while discovery continues in the serial worker."""

    config = config or StandConfig.load(args.config)
    client = WisdomSerialClient(
        port=args.port if port is None else port,
        baudrate=args.baud,
        timeout=args.serial_timeout,
        probe_timeout=args.probe_timeout,
    )
    logger = StandSessionLogger(
        args.log_dir,
        mode="hardware",
        config=config,
        flow="investigation",
    )
    controller = InvestigationController(
        config,
        client.send,
        mode="hardware",
        logger=logger,
    )
    return config, client, controller, logger


def _new_scene():
    return (
        StarField(350),
        Nebula(),
        CosmicDust(50),
        ShootingStars(),
    )


def run_game(args) -> int:
    if args.probe_timeout <= 0 or args.serial_timeout <= 0:
        raise SerialBridgeError("timeouts seriais devem ser positivos")

    config = StandConfig.load(args.config)
    init_display(windowed=args.windowed, windowed_size=config.windowed_size)
    config, serial_client, controller, logger = build_game_runtime(args, config=config)
    panel = GamePanel(
        serial_client,
        controller,
        diagnostic=args.diagnostic,
        startup_splash=not args.no_splash,
    )
    print("Interface aberta; procurando a BlackBoard Wisdom por HELLO...", flush=True)
    print(f"Log da partida: {logger.path}", flush=True)
    logger.write(
        "display_started",
        size=DISPLAY.surface.get_size(),
        windowed=bool(args.windowed),
        renderer="game-interface",
        requested_serial_port=args.port or "AUTO",
        discovery="background-worker",
        search_screen_enabled=not args.no_splash,
    )

    stars, nebula, dust, shooting_stars = _new_scene()
    running = True
    elapsed_visual = 0.0
    started_at = time.monotonic()
    try:
        while running:
            dt = DISPLAY.clock.tick(FPS) / 1000.0
            elapsed_visual += dt
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_q and (
                    pygame.key.get_mods() & pygame.KMOD_CTRL
                ):
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    args.windowed = not args.windowed
                    init_display(windowed=args.windowed, windowed_size=config.windowed_size)
                    stars, nebula, dust, shooting_stars = _new_scene()
                    logger.write("display_mode", windowed=args.windowed, size=DISPLAY.surface.get_size())
                else:
                    panel.handle_event(event)

            panel.update(dt)
            dust.update(dt)
            shooting_stars.update(dt)
            if DISPLAY.surface is None:
                raise RuntimeError("display não inicializado")
            DISPLAY.surface.fill(C_SPACE_BG)
            nebula.draw(DISPLAY.surface, elapsed_visual)
            stars.draw(DISPLAY.surface, elapsed_visual)
            dust.draw(DISPLAY.surface)
            shooting_stars.draw(DISPLAY.surface)
            panel.draw(DISPLAY.surface, elapsed_visual)
            pygame.display.flip()

            if (
                args.max_runtime_seconds is not None
                and time.monotonic() - started_at >= args.max_runtime_seconds
            ):
                running = False
    finally:
        active_exception = sys.exc_info()[0]
        try:
            panel.close()
        except Exception as cleanup_error:
            if active_exception is None:
                raise
            print(f"falha no cleanup: {cleanup_error}", file=sys.stderr)
        finally:
            try:
                logger.write(
                    "application_stopped",
                    state=controller.state.value,
                    completed_cycles=controller.completed_cycles,
                    renderer="game-interface",
                )
            finally:
                logger.close()
                pygame.quit()
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    while True:
        try:
            return run_game(args)
        except KeyboardInterrupt:
            return 130
        except SerialBridgeError as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"ERRO FATAL: {exc}", file=sys.stderr)
            traceback.print_exc()
            if not args.restart_on_crash:
                return 1
            print("Reiniciando o jogo em 2 segundos...", file=sys.stderr, flush=True)
            time.sleep(2.0)


__all__ = ("build_game_runtime", "build_parser", "main", "parse_args", "run_game")
