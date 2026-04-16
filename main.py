import os
import sys

# Allow `python main.py` with `src/` layout.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from report_building_agent.assistant import run_cli  # noqa: E402


if __name__ == "__main__":
    run_cli()
