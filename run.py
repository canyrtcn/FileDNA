"""GUI entry point for local development and Windows packaging."""

from pathlib import Path
import sys

# `python run.py` works even before installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from filedna.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
