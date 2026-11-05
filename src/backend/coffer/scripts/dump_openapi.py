import json
import sys
from pathlib import Path

from coffer.main import create_app


def main() -> None:
    path = Path(sys.argv[1])
    path.write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
