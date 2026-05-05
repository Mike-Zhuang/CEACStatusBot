import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import getSettings


def utcNowIso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def dictFactory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    fields = [column[0] for column in cursor.description]
    return {key: row[index] for index, key in enumerate(fields)}


@contextmanager
def getConnection() -> Iterator[sqlite3.Connection]:
    databasePath = getSettings().databasePath
    databasePath.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(databasePath)
    connection.row_factory = dictFactory
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initializeDatabase() -> None:
    with getConnection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_email_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS smtp_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                from_email TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                use_ssl INTEGER NOT NULL DEFAULT 1,
                password_encrypted TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS system_smtp_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                from_email TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                use_ssl INTEGER NOT NULL DEFAULT 1,
                password_encrypted TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ceac_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                location TEXT NOT NULL,
                application_num TEXT NOT NULL,
                passport_number TEXT NOT NULL,
                surname TEXT NOT NULL,
                receive_email TEXT NOT NULL,
                sender_mode TEXT NOT NULL DEFAULT 'system',
                is_enabled INTEGER NOT NULL DEFAULT 1,
                email_notifications_enabled INTEGER NOT NULL DEFAULT 1,
                next_check_at TEXT,
                last_checked_at TEXT,
                last_trigger_type TEXT,
                last_status_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (last_status_id) REFERENCES status_catalog(id)
            );

            CREATE TABLE IF NOT EXISTS status_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(status, description)
            );

            CREATE TABLE IF NOT EXISTS case_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                status_id INTEGER NOT NULL,
                ceac_last_updated TEXT NOT NULL DEFAULT '',
                visa_type TEXT NOT NULL DEFAULT '',
                case_created TEXT NOT NULL DEFAULT '',
                fetched_at TEXT NOT NULL,
                raw_payload TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES ceac_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (status_id) REFERENCES status_catalog(id)
            );

            CREATE TABLE IF NOT EXISTS query_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                success INTEGER NOT NULL,
                status_id INTEGER,
                error_message TEXT NOT NULL DEFAULT '',
                duration_ms INTEGER NOT NULL DEFAULT 0,
                trigger_type TEXT NOT NULL DEFAULT 'unknown',
                FOREIGN KEY (case_id) REFERENCES ceac_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (status_id) REFERENCES status_catalog(id)
            );

            CREATE TABLE IF NOT EXISTS query_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                trigger_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                locked_at TEXT,
                locked_by TEXT,
                started_at TEXT,
                finished_at TEXT,
                error_message TEXT NOT NULL DEFAULT '',
                result_json TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (case_id) REFERENCES ceac_cases(id) ON DELETE CASCADE
            );
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(ceac_cases)").fetchall()
        }
        if "email_notifications_enabled" not in columns:
            connection.execute(
                "ALTER TABLE ceac_cases ADD COLUMN email_notifications_enabled INTEGER NOT NULL DEFAULT 1",
            )
        if "last_trigger_type" not in columns:
            connection.execute(
                "ALTER TABLE ceac_cases ADD COLUMN last_trigger_type TEXT",
            )
        queryRunColumns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(query_runs)").fetchall()
        }
        if "trigger_type" not in queryRunColumns:
            connection.execute(
                "ALTER TABLE query_runs ADD COLUMN trigger_type TEXT NOT NULL DEFAULT 'unknown'",
            )
        queryJobColumns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(query_jobs)").fetchall()
        }
        if "result_json" not in queryJobColumns:
            connection.execute(
                "ALTER TABLE query_jobs ADD COLUMN result_json TEXT NOT NULL DEFAULT ''",
            )


def databaseExists() -> bool:
    return Path(getSettings().databasePath).exists()
