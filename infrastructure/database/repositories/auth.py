"""
Auth Repository
===============

Repository for user authentication, password-reset tokens, and recovery codes.
Extracted from UserAuthManager to keep SQL in the infrastructure layer.

Author: SYSGrow Team
Date: February 2026
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuthRepository:
    """Repository for user-authentication database operations."""

    def __init__(self, backend: Any) -> None:
        """
        Args:
            backend: Database handler exposing ``connection()`` and
                     ``get_db()`` context managers (SQLiteDatabaseHandler).
        """
        self._backend = backend

    # ------------------------------------------------------------------
    # User lookup
    # ------------------------------------------------------------------

    def create_user(self, username: str, password_hash: str) -> bool:
        """Create a user account. Returns *True* on success."""
        try:
            with self._backend.connection() as db:
                db.execute(
                    "INSERT INTO Users (username, password_hash) VALUES (?, ?)",
                    (username.strip(), password_hash),
                )
                db.commit()
                return True
        except Exception as e:
            logger.error("create_user failed: %s", e)
            return False

    def get_user_auth_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Return ``{id, username, password_hash, email}`` or *None*."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    # Keep auth lookup compatible with older schemas that do not yet include Users.email.
                    "SELECT id, username, password_hash FROM Users WHERE username = ?",
                    (username.strip(),),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "username": row[1],
                    "password_hash": row[2],
                    "email": None,
                }
        except Exception as e:
            logger.error("get_user_auth_by_username failed: %s", e)
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Return ``{id, username, email}`` or *None*."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "SELECT id, username, email FROM Users WHERE email = ?",
                    (email.lower().strip(),),
                )
                row = cursor.fetchone()
                if row:
                    return {"id": row[0], "username": row[1], "email": row[2]}
                return None
        except Exception as e:
            logger.error("get_user_by_email failed: %s", e)
            return None

    def get_user_by_username_with_email(self, username: str) -> Optional[Dict[str, Any]]:
        """Return ``{id, username, email}`` or *None*."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "SELECT id, username, email FROM Users WHERE username = ?",
                    (username.strip(),),
                )
                row = cursor.fetchone()
                if row:
                    return {"id": row[0], "username": row[1], "email": row[2]}
                return None
        except Exception as e:
            logger.error("get_user_by_username_with_email failed: %s", e)
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Return ``{id, username, email}`` or *None*."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "SELECT id, username, email FROM Users WHERE id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                if row:
                    return {"id": row[0], "username": row[1], "email": row[2]}
                return None
        except Exception as e:
            logger.error("get_user_by_id failed: %s", e)
            return None

    def update_email(self, user_id: int, email: str) -> bool:
        """Update a user's e-mail address.  Returns *True* on success."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "UPDATE Users SET email = ? WHERE id = ?",
                    (email.lower().strip(), user_id),
                )
                if cursor.rowcount != 1:
                    db.rollback()
                    logger.warning("update_email failed: user %s not found", user_id)
                    return False
                db.commit()
                return True
        except Exception as e:
            logger.error("update_email failed: %s", e)
            return False

    def update_password(self, user_id: int, password_hash: str) -> bool:
        """Update a user's password hash.  Returns *True* on success."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "UPDATE Users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id),
                )
                if cursor.rowcount != 1:
                    db.rollback()
                    logger.warning("update_password failed: user %s not found", user_id)
                    return False
                db.commit()
                return True
        except Exception as e:
            logger.error("update_password failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Password-reset tokens
    # ------------------------------------------------------------------

    def create_reset_token(
        self, user_id: int, token_hash: str, expires_at_iso: str,
    ) -> bool:
        """Delete existing tokens for *user_id* and insert a new one."""
        try:
            with self._backend.connection() as db:
                try:
                    db.execute(
                        "DELETE FROM PasswordResetTokens WHERE user_id = ?",
                        (user_id,),
                    )
                    db.execute(
                        """
                        INSERT INTO PasswordResetTokens (user_id, token_hash, expires_at)
                        VALUES (?, ?, ?)
                        """,
                        (user_id, token_hash, expires_at_iso),
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            return True
        except Exception as e:
            logger.error("create_reset_token failed: %s", e)
            return False

    def find_reset_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Return token row joined with Users, or *None*."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    """
                    SELECT prt.id, prt.user_id, prt.expires_at, prt.used_at,
                           u.username, u.email
                    FROM PasswordResetTokens prt
                    JOIN Users u ON u.id = prt.user_id
                    WHERE prt.token_hash = ?
                    """,
                    (token_hash,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "token_id": row[0],
                    "user_id": row[1],
                    "expires_at": row[2],
                    "used_at": row[3],
                    "username": row[4],
                    "email": row[5],
                }
        except Exception as e:
            logger.error("find_reset_token failed: %s", e)
            return None

    def mark_token_used(self, token_id: int, used_at_iso: str) -> bool:
        """Mark a token as consumed."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "UPDATE PasswordResetTokens SET used_at = ? WHERE id = ?",
                    (used_at_iso, token_id),
                )
                if cursor.rowcount != 1:
                    db.rollback()
                    logger.warning("mark_token_used failed: token %s not found", token_id)
                    return False
                db.commit()
            return True
        except Exception as e:
            logger.error("mark_token_used failed: %s", e)
            return False

    def use_reset_token_and_update_password(
        self,
        user_id: int,
        token_id: int,
        password_hash: str,
        used_at_iso: str,
    ) -> bool:
        """Atomically update password and consume a reset token.

        Returns *True* only when both writes succeed.
        """
        try:
            with self._backend.connection() as db:
                try:
                    user_cursor = db.execute(
                        "SELECT 1 FROM Users WHERE id = ?",
                        (user_id,),
                    )
                    if user_cursor.fetchone() is None:
                        db.rollback()
                        logger.warning(
                            "use_reset_token_and_update_password failed: user %s not found",
                            user_id,
                        )
                        return False

                    db.execute(
                        "UPDATE Users SET password_hash = ? WHERE id = ?",
                        (password_hash, user_id),
                    )
                    token_cursor = db.execute(
                        """
                        UPDATE PasswordResetTokens
                        SET used_at = ?
                        WHERE id = ? AND user_id = ? AND used_at IS NULL
                        """,
                        (used_at_iso, token_id, user_id),
                    )
                    if token_cursor.rowcount != 1:
                        db.rollback()
                        logger.warning(
                            "use_reset_token_and_update_password failed: token %s not consumable for user %s",
                            token_id,
                            user_id,
                        )
                        return False

                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            return True
        except Exception as e:
            logger.error("use_reset_token_and_update_password failed: %s", e)
            return False

    def cleanup_expired_tokens(self, cutoff_iso: str) -> int:
        """Delete expired tokens.  Returns count of deleted rows."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "DELETE FROM PasswordResetTokens WHERE expires_at < ?",
                    (cutoff_iso,),
                )
                deleted = cursor.rowcount
                db.commit()
                return deleted
        except Exception as e:
            logger.error("cleanup_expired_tokens failed: %s", e)
            return 0

    # ------------------------------------------------------------------
    # Recovery codes
    # ------------------------------------------------------------------

    def replace_recovery_codes(
        self, user_id: int, code_hashes: List[str], created_at_iso: str,
    ) -> bool:
        """Delete old codes and insert fresh ones.  Returns *True* on success."""
        try:
            with self._backend.connection() as db:
                try:
                    db.execute(
                        "DELETE FROM RecoveryCodes WHERE user_id = ?",
                        (user_id,),
                    )
                    for code_hash in code_hashes:
                        db.execute(
                            """
                            INSERT INTO RecoveryCodes (user_id, code_hash, created_at)
                            VALUES (?, ?, ?)
                            """,
                            (user_id, code_hash, created_at_iso),
                        )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            return True
        except Exception as e:
            logger.error("replace_recovery_codes failed: %s", e)
            return False

    def find_unused_recovery_code(
        self, user_id: int, code_hash: str,
    ) -> Optional[int]:
        """Return the ``code_id`` if valid & unused, else *None*."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    """
                    SELECT code_id FROM RecoveryCodes
                    WHERE user_id = ? AND code_hash = ? AND used_at IS NULL
                    """,
                    (user_id, code_hash),
                )
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error("find_unused_recovery_code failed: %s", e)
            return None

    def mark_recovery_code_used(self, code_id: int, used_at_iso: str) -> bool:
        """Mark a recovery code as consumed."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    "UPDATE RecoveryCodes SET used_at = ? WHERE code_id = ?",
                    (used_at_iso, code_id),
                )
                if cursor.rowcount != 1:
                    db.rollback()
                    logger.warning("mark_recovery_code_used failed: code %s not found", code_id)
                    return False
                db.commit()
            return True
        except Exception as e:
            logger.error("mark_recovery_code_used failed: %s", e)
            return False

    def count_unused_recovery_codes(self, user_id: int) -> int:
        """Return the number of unused recovery codes for a user."""
        try:
            with self._backend.connection() as db:
                cursor = db.execute(
                    """
                    SELECT COUNT(*) FROM RecoveryCodes
                    WHERE user_id = ? AND used_at IS NULL
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error("count_unused_recovery_codes failed: %s", e)
            return 0

    def use_recovery_code_and_reset_password(
        self,
        user_id: int,
        code_hash: str,
        password_hash: str,
        used_at_iso: str,
    ) -> bool:
        """Atomically validate code, update password, and mark code used.

        Returns *True* on success, *False* if code not found or error.
        """
        try:
            with self._backend.connection() as db:
                try:
                    cursor = db.execute(
                        """
                        SELECT code_id FROM RecoveryCodes
                        WHERE user_id = ? AND code_hash = ? AND used_at IS NULL
                        """,
                        (user_id, code_hash),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False
                    code_id = row[0]

                    user_cursor = db.execute(
                        "UPDATE Users SET password_hash = ? WHERE id = ?",
                        (password_hash, user_id),
                    )
                    if user_cursor.rowcount != 1:
                        db.rollback()
                        logger.warning(
                            "use_recovery_code_and_reset_password failed: user %s not found",
                            user_id,
                        )
                        return False

                    code_cursor = db.execute(
                        "UPDATE RecoveryCodes SET used_at = ? WHERE code_id = ?",
                        (used_at_iso, code_id),
                    )
                    if code_cursor.rowcount != 1:
                        db.rollback()
                        logger.warning(
                            "use_recovery_code_and_reset_password failed: code %s not consumable",
                            code_id,
                        )
                        return False
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            return True
        except Exception as e:
            logger.error("use_recovery_code_and_reset_password failed: %s", e)
            return False
