"""
auth_model.py — Credential storage and validation for PMO Suite.

• Passwords are stored as PBKDF2-HMAC-SHA256 hashes (600 000 iterations).
• A default 'admin / admin123' account is seeded on first run.
• Public API: validate_login(username, password) → bool
              get_user(username)                  → dict | None
              create_user(username, password, role) → None
              change_password(username, old, new)   → bool
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from app.database.db_manager import get_connection

# ── Constants ────────────────────────────────────────────────────────────────
_ITERATIONS = 600_000
_ALGORITHM  = "sha256"
_SALT_BYTES = 32


# ── Helpers ───────────────────────────────────────────────────────────────────
def _hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Return (salt, hash).  Pass an existing salt to verify a stored hash."""
    if salt is None:
        salt = os.urandom(_SALT_BYTES)
    key = hashlib.pbkdf2_hmac(
        _ALGORITHM,
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
    )
    return salt, key


def _verify_password(password: str, stored_salt_hex: str, stored_hash_hex: str) -> bool:
    salt       = bytes.fromhex(stored_salt_hex)
    stored_key = bytes.fromhex(stored_hash_hex)
    _, computed = _hash_password(password, salt)
    return hmac.compare_digest(computed, stored_key)


# ── DB schema ─────────────────────────────────────────────────────────────────
def initialize_auth_tables() -> None:
    """Create users table and seed default admin if empty."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            salt_hex     TEXT    NOT NULL,
            hash_hex     TEXT    NOT NULL,
            role         TEXT    NOT NULL DEFAULT 'user',
            display_name TEXT,
            created_at   TEXT    DEFAULT (datetime('now')),
            last_login   TEXT
        )
    """)
    conn.commit()

    # Seed default admin if no users exist yet
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        _create_user_internal(conn, "admin", "admin123", "admin", "Administrator")


def _create_user_internal(conn: sqlite3.Connection,
                           username: str, password: str,
                           role: str = "user",
                           display_name: str = "") -> None:
    salt, key = _hash_password(password)
    conn.execute(
        "INSERT INTO users (username, salt_hex, hash_hex, role, display_name) "
        "VALUES (?, ?, ?, ?, ?)",
        (username, salt.hex(), key.hex(), role, display_name or username),
    )
    conn.commit()


# ── Public API ────────────────────────────────────────────────────────────────
def validate_login(username: str, password: str) -> bool:
    """Return True if credentials are valid."""
    if not username or not password:
        return False
    conn = get_connection()
    row  = conn.execute(
        "SELECT salt_hex, hash_hex FROM users WHERE username=? COLLATE NOCASE",
        (username,),
    ).fetchone()
    if row is None:
        return False
    ok = _verify_password(password, row["salt_hex"], row["hash_hex"])
    if ok:
        conn.execute(
            "UPDATE users SET last_login=datetime('now') WHERE username=? COLLATE NOCASE",
            (username,),
        )
        conn.commit()
    return ok


def get_user(username: str) -> dict | None:
    conn = get_connection()
    row  = conn.execute(
        "SELECT id, username, role, display_name, last_login "
        "FROM users WHERE username=? COLLATE NOCASE",
        (username,),
    ).fetchone()
    return dict(row) if row else None


def create_user(username: str, password: str,
                role: str = "user", display_name: str = "") -> None:
    conn = get_connection()
    _create_user_internal(conn, username, password, role, display_name)


def change_password(username: str, old_password: str, new_password: str) -> bool:
    if not validate_login(username, old_password):
        return False
    conn = get_connection()
    salt, key = _hash_password(new_password)
    conn.execute(
        "UPDATE users SET salt_hex=?, hash_hex=? WHERE username=? COLLATE NOCASE",
        (salt.hex(), key.hex(), username),
    )
    conn.commit()
    return True
