"""Database-level guarantees: migrations match the models, and backups are real, pruned copies."""

import datetime as dt
import sqlite3
from contextlib import closing

from alembic import command

from bot.db.engine import alembic_config
from bot.services.backup import backup_database


def test_migrations_match_models(tmp_path):
    config = alembic_config(str(tmp_path / "migrated.db"))
    command.upgrade(config, "head")
    command.check(config)  # raises if models and migrations have drifted apart


def test_backup_copies_database_and_prunes_old_copies(tmp_path):
    db_path = tmp_path / "live.db"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES ('kept')")
        conn.commit()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "nadbavki_2026-01-01.db").write_bytes(b"old")
    (backup_dir / "nadbavki_2026-09-10.db").write_bytes(b"recent")

    target = backup_database(str(db_path), backup_dir, dt.date(2026, 9, 15), keep_days=30)

    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute("SELECT v FROM t").fetchall() == [("kept",)]
    assert sorted(p.name for p in backup_dir.iterdir()) == ["nadbavki_2026-09-10.db", "nadbavki_2026-09-15.db"]
