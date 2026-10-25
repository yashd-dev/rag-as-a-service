"""Process durable private upload jobs. Run separately from Flask."""

import argparse
import logging
import time

from backend.app.config import Config
from backend.app.services.ingestion_worker import run_once


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    config = {name: getattr(Config, name) for name in dir(Config) if name.isupper()}
    while True:
        try:
            worked = run_once(config)
        except Exception as exc:  # noqa: BLE001 - keep the worker alive on store outages
            logging.getLogger(__name__).error("Worker unavailable: %s", type(exc).__name__)
            if args.once:
                raise SystemExit(1) from None
            worked = False
        if args.once:
            break
        if not worked:
            time.sleep(2)


if __name__ == "__main__":
    main()
