"""Prepare an isolated judging dataset via the application's normal business endpoints."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def seed_demo_history(connection):
    """Populate only an empty competition history, atomically across restarts."""
    rows = [
        # RFQ, inquiry date, customer, urgency, line, part, deadline
        ("DEMO-0901", "2026-09-04", "合成客户·星河", "AOG", 1, "PN-0001", "2026-09-10"),
        ("DEMO-0902", "2026-09-23", "合成客户·云帆", "NORMAL", 1, "PN-0002", "2026-09-30"),
        ("DEMO-1001", "2026-10-15", "合成客户·星河", "NORMAL", 1, "PN-0002", "2026-10-24"),
        ("DEMO-1002", "2026-10-26", "合成客户·远航", "URGENT", 1, "PN-0001", "2026-10-30"),
        ("DEMO-1101", "2026-11-09", "合成客户·云帆", "USR", 1, "PN-0002", "2026-11-12"),
        ("DEMO-1102", "2026-11-10", "合成客户·星河", "AOG", 1, "PN-0001", "2026-11-13"),
        ("DEMO-1102", "2026-11-10", "合成客户·星河", "AOG", 2, "PN-0003", "2026-11-13"),
    ]
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM historical LIMIT 1").fetchone():
            return
        connection.executemany(
            "INSERT INTO historical (rfq_no, inquiry_date, airline, urgency, line_no, "
            "part_number, deadline, inquiry_no, source_row, quantity, unit) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'EA')",
            [(*row, row[0], f"competition-demo/{row[0]}/{row[4]}") for row in rows],
        )


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
