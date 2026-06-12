"""One-line logging configuration for CLI entry points."""

from __future__ import annotations

import logging
import sys


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # nba_api's HTTP layer is chatty; keep it quiet unless debugging.
    if not verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
