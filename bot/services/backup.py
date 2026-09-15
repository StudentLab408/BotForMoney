import datetime as dt
import sqlite3
from contextlib import closing
from pathlib import Path

BACKUP_PATTERN = "nadbavki_*.db"


def backup_database(db_path: str, backup_dir: Path, today: dt.date, keep_days: int) -> Path:
    """Copy the live database with SQLite's online backup API and delete copies older than keep_days."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"nadbavki_{today:%Y-%m-%d}.db"
    with closing(sqlite3.connect(db_path)) as source, closing(sqlite3.connect(target)) as destination:
        source.backup(destination)

    oldest_kept = today - dt.timedelta(days=keep_days)
    for old in backup_dir.glob(BACKUP_PATTERN):
        try:
            copy_date = dt.datetime.strptime(old.stem.removeprefix("nadbavki_"), "%Y-%m-%d").date()
        except ValueError:
            continue
        if copy_date < oldest_kept:
            old.unlink()
    return target
