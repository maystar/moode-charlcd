"""Command line entry point: ``moode-charlcd [--config FILE]``."""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from pathlib import Path

from . import __version__
from .app import build_app
from .config import DEFAULT_PATH, load_config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="moode-charlcd", description="Show moOde playback information on a character LCD."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_PATH,
        help=f"configuration file (default: {DEFAULT_PATH})",
    )
    parser.add_argument(
        "--display", choices=["hd44780-pcf8574", "console"], help="override the display driver"
    )
    parser.add_argument(
        "--console", action="store_true", help="additionally mirror the display to the console"
    )
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ...")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s [%(name)s] %(message)s")
    logging.getLogger("mpd").setLevel(logging.WARNING)  # python-mpd2 logs every call
    config = load_config(args.config)
    if args.display:
        config["display"]["driver"] = args.display

    app = build_app(config, console_mirror=args.console)

    stop = threading.Event()

    def request_stop(signum: int, _frame: object) -> None:
        logging.getLogger(__name__).info("Received signal %d, stopping", signum)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    app.run(stop)


if __name__ == "__main__":
    main()
