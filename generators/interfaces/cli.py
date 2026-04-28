import logging
import sys
from pathlib import Path

from application.streaming_generator import StreamingGenerator
from common.config import load_config

log = logging.getLogger("generator")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if not (root / "common" / "config.py").is_file():
        log.error(
            "Generator bundle not found under %s (missing common/config.py). "
            "Run `docker compose` from the DataOpsShowcase directory so the image "
            "contains the code, or rebuild techmart/data-generator:local.",
            root,
        )
        return 1
    cfg = load_config()
    StreamingGenerator(cfg).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
