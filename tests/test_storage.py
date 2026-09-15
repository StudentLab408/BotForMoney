"""Database-level guarantees: migrations match the models, and backups are real, pruned copies."""

import datetime as dt
import sqlite3
from contextlib import closing

import pytest
from alembic import command

from bot.db.engine import alembic_config, dispose_engine, init_database
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


def _tables(db_path) -> set[str]:
    with closing(sqlite3.connect(db_path)) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_failed_migration_rolls_back_completely(tmp_path):
    db_path = tmp_path / "conflict.db"
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("CREATE TABLE supplements (id INTEGER PRIMARY KEY)")  # clashes midway through 0001
        conn.commit()

    with pytest.raises(Exception, match="already exists"):
        command.upgrade(alembic_config(str(db_path)), "head")

    assert "fsm_records" not in _tables(db_path) and "users" not in _tables(db_path)


async def test_database_created_without_migrations_is_moved_aside(tmp_path):
    db_path = tmp_path / "nadbavki.db"
    with closing(sqlite3.connect(db_path)) as conn:  # what the pre-Alembic bot version left behind
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, telegram_id INTEGER)")
        conn.execute("INSERT INTO users (telegram_id) VALUES (42)")
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")  # left by a failed run
        conn.commit()

    await init_database(str(db_path))
    await dispose_engine()

    [old] = [p for p in tmp_path.iterdir() if p.name.startswith("nadbavki.pre-migrations-")]
    with closing(sqlite3.connect(old)) as conn:
        assert conn.execute("SELECT telegram_id FROM users").fetchall() == [(42,)]
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [("0001",)]


async def test_migrated_database_is_left_in_place(tmp_path):
    db_path = tmp_path / "nadbavki.db"
    await init_database(str(db_path))
    await dispose_engine()
    await init_database(str(db_path))
    await dispose_engine()
    assert [p.name for p in tmp_path.iterdir() if "pre-migrations" in p.name] == []
