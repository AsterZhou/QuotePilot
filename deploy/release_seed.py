"""Prepare an isolated judging dataset via the application's normal business endpoints."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build_seed(destination):
    import server
    from scripts.business_cycle import run_cycle

    def save(_approved_quote):
        with sqlite3.connect(server.DB) as source, sqlite3.connect(destination) as target:
            source.backup(target)
    run_cycle(approved_sink=save)


def install_seed(source, destination):
    """Install atomically only on a new volume. Never replace existing data."""
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent, prefix='.qp-seed-')
    os.close(fd)
    try:
        with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as src, sqlite3.connect(temporary) as dst:
            src.backup(dst)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            pass
    finally:
        os.unlink(temporary)


if __name__ == '__main__':
    build_seed(Path(sys.argv[1]))
