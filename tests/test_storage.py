"""Database-level guarantees: migrations match the models, and backups are real, pruned copies."""

import datetime as dt
import sqlite3
from contextlib import closing

import pytest
from alembic import command
from alembic.script import ScriptDirectory

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


def _head(db_path) -> str:
    return ScriptDirectory.from_config(alembic_config(str(db_path))).get_current_head()


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
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [(_head(db_path),)]


async def test_migrated_database_is_left_in_place(tmp_path):
    db_path = tmp_path / "nadbavki.db"
    await init_database(str(db_path))
    await dispose_engine()
    await init_database(str(db_path))
    await dispose_engine()
    assert [p.name for p in tmp_path.iterdir() if "pre-migrations" in p.name] == []


def test_unique_index_migration_closes_existing_duplicates(tmp_path):
    db_path = tmp_path / "dups.db"
    config = alembic_config(str(db_path))
    command.upgrade(config, "0001")
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO users (id, telegram_id, last_name, first_name, middle_name, group_number, role) "
            "VALUES (1, 1, 'A', 'B', 'C', 'g', 'student')"
        )
        conn.execute("INSERT INTO events (id, kind, name, held_on) VALUES (1, 'conference', 'C', '2026-09-01')")
        conn.execute("INSERT INTO projects (id, name) VALUES (1, 'P')")
        rows = [(1, "pending"), (2, "approved"), (3, "approved"), (4, "rejected")]
        for supplement_id, status in rows:
            conn.execute(
                "INSERT INTO supplements (id, student_id, event_id, status, submitted_by) VALUES (?, 1, 1, ?, 1)",
                (supplement_id, status),
            )
        conn.execute("INSERT INTO project_members (id, project_id, user_id, start_period) VALUES (1, 1, 1, 100)")
        conn.execute("INSERT INTO project_members (id, project_id, user_id, start_period) VALUES (2, 1, 1, 101)")
        conn.commit()

    command.upgrade(config, "head")

    with closing(sqlite3.connect(db_path)) as conn:
        statuses = dict(conn.execute("SELECT id, status FROM supplements"))
        members = dict(conn.execute("SELECT id, end_period FROM project_members"))
    assert statuses == {1: "withdrawn", 2: "approved", 3: "cancelled", 4: "rejected"}
    assert members == {1: None, 2: 101}


def test_participation_migration_keeps_old_project_names(tmp_path):
    db_path = tmp_path / "old.db"
    config = alembic_config(str(db_path))
    command.upgrade(config, "0003")
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO users (id, telegram_id, last_name, first_name, middle_name, group_number, role) "
            "VALUES (1, 1, 'A', 'B', 'C', 'g', 'student')"
        )
        conn.execute("INSERT INTO events (id, kind, name, held_on) VALUES (1, 'conference', 'C', '2026-09-01')")
        conn.execute("INSERT INTO events (id, kind, name, held_on) VALUES (2, 'event', 'E', '2026-09-01')")
        conn.execute(
            "INSERT INTO supplements (id, student_id, event_id, status, project_name, submitted_by) "
            "VALUES (1, 1, 1, 'pending', 'RoboArm', 1)"
        )
        conn.execute(
            "INSERT INTO supplements (id, student_id, event_id, status, what_did, submitted_by) "
            "VALUES (2, 1, 2, 'pending', 'helped', 1)"
        )
        conn.commit()

    command.upgrade(config, "head")

    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT id, participation, work_title, what_did FROM supplements ORDER BY id").fetchall()
    assert rows == [(1, "project", "RoboArm", None), (2, None, None, "helped")]
