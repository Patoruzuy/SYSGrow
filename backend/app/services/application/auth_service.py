"""
User Authentication Service
===========================
Manages user authentication with bcrypt hashing and audit logging.
Includes password recovery functionality with secure token generation.

Moved from root auth_manager.py to app/services/auth.py for better organization.
"""

import bcrypt
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from infrastructure.logging.audit import AuditLogger

# Password reset token settings
RESET_TOKEN_EXPIRY_HOURS = 1  # Token valid for 1 hour
RESET_TOKEN_LENGTH = 32  # 32 bytes = 64 hex characters

# Recovery code settings
RECOVERY_CODE_COUNT = 10  # Number of recovery codes per user
RECOVERY_CODE_LENGTH = 8  # Format: XXXX-XXXX (4+4 characters)
# Unambiguous character set (excludes 0/O, 1/I/l)
RECOVERY_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass
class UserAuthManager:
    """
    Manages user authentication with bcrypt hashing and audit logging.
    """

    database_handler: any
    audit_logger: Optional[AuditLogger] = None
    max_failed_attempts: int = 5

    def hash_password(self, password: str) -> str:
        """Hash the provided password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed_password.decode("utf-8")

    def check_password(self, stored_password: str, provided_password: str) -> bool:
        """Validate a plaintext password against the stored hash."""
        return bcrypt.checkpw(provided_password.encode("utf-8"), stored_password.encode("utf-8"))

    def register_user(self, username: str, password: str) -> bool:
        password_hash = self.hash_password(password)
        try:
            self.database_handler.insert_user(username, password_hash)
            logging.info("User '%s' registered successfully.", username)
            if self.audit_logger:
                self.audit_logger.log_event(actor=username, action="register", resource="user", outcome="success")
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logging.error("Error registering user '%s': %s", username, exc)
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=username,
                    action="register",
                    resource="user",
                    outcome="error",
                    error=str(exc),
                )
            return False

    def authenticate_user(self, username: str, password: str) -> bool:
        user = self.database_handler.get_user_by_username(username)
        if not user:
            logging.warning("Authentication failed for user '%s': user not found.", username)
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=username,
                    action="login",
                    resource="user",
                    outcome="not_found",
                )
            return False

        stored_password = user["password_hash"]
        if not self.check_password(stored_password, password):
            logging.warning("Authentication failed for user '%s': invalid credentials.", username)
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=username,
                    action="login",
                    resource="user",
                    outcome="denied",
                )
            return False

        logging.info("User '%s' authenticated successfully.", username)
        if self.audit_logger:
            self.audit_logger.log_event(
                actor=username,
                action="login",
                resource="user",
                outcome="success",
            )
        return True

    # --- Password Recovery Methods ---

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email address."""
        try:
            with self.database_handler.connection() as db:
                cursor = db.execute(
                    "SELECT id, username, email FROM Users WHERE email = ?",
                    (email.lower().strip(),)
                )
                row = cursor.fetchone()
                if row:
                    return {"id": row[0], "username": row[1], "email": row[2]}
                return None
        except Exception as e:
            logging.error(f"Error fetching user by email: {e}")
            return None

    def get_user_by_username_with_email(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user with email by username."""
        try:
            with self.database_handler.connection() as db:
                cursor = db.execute(
                    "SELECT id, username, email FROM Users WHERE username = ?",
                    (username.strip(),)
                )
                row = cursor.fetchone()
                if row:
                    return {"id": row[0], "username": row[1], "email": row[2]}
                return None
        except Exception as e:
            logging.error(f"Error fetching user by username: {e}")
            return None

    def update_user_email(self, user_id: int, email: str) -> bool:
        """Update user's email address."""
        try:
            with self.database_handler.connection() as db:
                db.execute(
                    "UPDATE Users SET email = ? WHERE id = ?",
                    (email.lower().strip(), user_id)
                )
                db.commit()
                logging.info(f"Updated email for user ID {user_id}")
                return True
        except Exception as e:
            logging.error(f"Error updating user email: {e}")
            return False

    def generate_reset_token(self, user_id: int) -> Optional[str]:
        """
        Generate a secure password reset token for a user.

        Returns the plain token (to be sent to user) - only the hash is stored.
        """
        try:
            # Generate a cryptographically secure token
            token = secrets.token_hex(RESET_TOKEN_LENGTH)
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            # Calculate expiration time
            expires_at = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)

            with self.database_handler.connection() as db:
                # Invalidate any existing tokens for this user
                db.execute(
                    "DELETE FROM PasswordResetTokens WHERE user_id = ?",
                    (user_id,)
                )

                # Insert new token
                db.execute(
                    """
                    INSERT INTO PasswordResetTokens (user_id, token_hash, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, token_hash, expires_at.isoformat())
                )
                db.commit()

            logging.info(f"Generated password reset token for user ID {user_id}")
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=str(user_id),
                    action="password_reset_request",
                    resource="user",
                    outcome="success",
                )

            return token

        except Exception as e:
            logging.error(f"Error generating reset token: {e}")
            return None

    def validate_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a password reset token.

        Returns user info if token is valid, None otherwise.
        """
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            with self.database_handler.connection() as db:
                cursor = db.execute(
                    """
                    SELECT prt.id, prt.user_id, prt.expires_at, prt.used_at,
                           u.username, u.email
                    FROM PasswordResetTokens prt
                    JOIN Users u ON u.id = prt.user_id
                    WHERE prt.token_hash = ?
                    """,
                    (token_hash,)
                )
                row = cursor.fetchone()

                if not row:
                    logging.warning("Invalid password reset token attempted")
                    return None

                token_id, user_id, expires_at_str, used_at, username, email = row

                # Check if token was already used
                if used_at:
                    logging.warning(f"Attempted to use already-used reset token for user {username}")
                    return None

                # Check if token is expired
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.utcnow() > expires_at:
                    logging.warning(f"Expired reset token attempted for user {username}")
                    return None

                return {
                    "token_id": token_id,
                    "user_id": user_id,
                    "username": username,
                    "email": email,
                }

        except Exception as e:
            logging.error(f"Error validating reset token: {e}")
            return None

    def reset_password_with_token(self, token: str, new_password: str) -> bool:
        """
        Reset a user's password using a valid reset token.

        Returns True if password was reset successfully.
        """
        try:
            # Validate token first
            token_info = self.validate_reset_token(token)
            if not token_info:
                return False

            user_id = token_info["user_id"]
            username = token_info["username"]
            token_id = token_info["token_id"]

            # Hash the new password
            password_hash = self.hash_password(new_password)

            with self.database_handler.connection() as db:
                # Update password
                db.execute(
                    "UPDATE Users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id)
                )

                # Mark token as used
                db.execute(
                    "UPDATE PasswordResetTokens SET used_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), token_id)
                )

                db.commit()

            logging.info(f"Password reset successful for user '{username}'")
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=username,
                    action="password_reset",
                    resource="user",
                    outcome="success",
                )

            return True

        except Exception as e:
            logging.error(f"Error resetting password: {e}")
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor="unknown",
                    action="password_reset",
                    resource="user",
                    outcome="error",
                    error=str(e),
                )
            return False

    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired password reset tokens from the database.

        Returns the number of tokens removed.
        """
        try:
            with self.database_handler.connection() as db:
                cursor = db.execute(
                    "DELETE FROM PasswordResetTokens WHERE expires_at < ?",
                    (datetime.utcnow().isoformat(),)
                )
                deleted = cursor.rowcount
                db.commit()

                if deleted > 0:
                    logging.info(f"Cleaned up {deleted} expired password reset tokens")

                return deleted

        except Exception as e:
            logging.error(f"Error cleaning up expired tokens: {e}")
            return 0

    # --- Recovery Code Methods ---

    def _generate_single_code(self) -> str:
        """Generate a single recovery code in XXXX-XXXX format."""
        part1 = ''.join(secrets.choice(RECOVERY_CODE_CHARS) for _ in range(4))
        part2 = ''.join(secrets.choice(RECOVERY_CODE_CHARS) for _ in range(4))
        return f"{part1}-{part2}"

    def generate_recovery_codes(self, user_id: int) -> Optional[List[str]]:
        """
        Generate new recovery codes for a user.

        Invalidates any existing codes and generates fresh ones.
        Returns the plain codes (to be shown to user once).
        Only the hashes are stored in the database.
        """
        try:
            codes = []
            code_hashes = []

            # Generate codes and their hashes
            for _ in range(RECOVERY_CODE_COUNT):
                code = self._generate_single_code()
                code_hash = hashlib.sha256(code.upper().encode()).hexdigest()
                codes.append(code)
                code_hashes.append(code_hash)

            with self.database_handler.connection() as db:
                # Delete existing codes for this user
                db.execute(
                    "DELETE FROM RecoveryCodes WHERE user_id = ?",
                    (user_id,)
                )

                # Insert new codes
                for code_hash in code_hashes:
                    db.execute(
                        """
                        INSERT INTO RecoveryCodes (user_id, code_hash, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (user_id, code_hash, datetime.utcnow().isoformat())
                    )
                db.commit()

            logging.info(f"Generated {RECOVERY_CODE_COUNT} recovery codes for user ID {user_id}")
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=str(user_id),
                    action="recovery_codes_generated",
                    resource="user",
                    outcome="success",
                )

            return codes

        except Exception as e:
            logging.error(f"Error generating recovery codes: {e}")
            return None

    def validate_recovery_code(self, user_id: int, code: str) -> bool:
        """
        Check if a recovery code is valid and unused for the given user.

        Returns True if valid, False otherwise.
        """
        try:
            # Normalize the code (uppercase, remove spaces)
            normalized_code = code.upper().replace(" ", "").replace("-", "")
            # Re-add the dash for consistent format
            if len(normalized_code) == 8:
                normalized_code = f"{normalized_code[:4]}-{normalized_code[4:]}"

            code_hash = hashlib.sha256(normalized_code.encode()).hexdigest()

            with self.database_handler.connection() as db:
                cursor = db.execute(
                    """
                    SELECT code_id FROM RecoveryCodes
                    WHERE user_id = ? AND code_hash = ? AND used_at IS NULL
                    """,
                    (user_id, code_hash)
                )
                return cursor.fetchone() is not None

        except Exception as e:
            logging.error(f"Error validating recovery code: {e}")
            return False

    def reset_password_with_recovery_code(
        self, user_id: int, code: str, new_password: str
    ) -> bool:
        """
        Reset a user's password using a valid recovery code.

        The code is marked as used after successful password reset.
        Returns True if password was reset successfully.
        """
        try:
            # Normalize the code
            normalized_code = code.upper().replace(" ", "").replace("-", "")
            if len(normalized_code) == 8:
                normalized_code = f"{normalized_code[:4]}-{normalized_code[4:]}"

            code_hash = hashlib.sha256(normalized_code.encode()).hexdigest()

            with self.database_handler.connection() as db:
                # Find the unused code
                cursor = db.execute(
                    """
                    SELECT code_id FROM RecoveryCodes
                    WHERE user_id = ? AND code_hash = ? AND used_at IS NULL
                    """,
                    (user_id, code_hash)
                )
                row = cursor.fetchone()

                if not row:
                    logging.warning(f"Invalid or used recovery code attempted for user ID {user_id}")
                    return False

                code_id = row[0]

                # Hash the new password
                password_hash = self.hash_password(new_password)

                # Update password
                db.execute(
                    "UPDATE Users SET password_hash = ? WHERE id = ?",
                    (password_hash, user_id)
                )

                # Mark code as used
                db.execute(
                    "UPDATE RecoveryCodes SET used_at = ? WHERE code_id = ?",
                    (datetime.utcnow().isoformat(), code_id)
                )

                db.commit()

            logging.info(f"Password reset successful via recovery code for user ID {user_id}")
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=str(user_id),
                    action="password_reset_recovery_code",
                    resource="user",
                    outcome="success",
                )

            return True

        except Exception as e:
            logging.error(f"Error resetting password with recovery code: {e}")
            if self.audit_logger:
                self.audit_logger.log_event(
                    actor=str(user_id),
                    action="password_reset_recovery_code",
                    resource="user",
                    outcome="error",
                    error=str(e),
                )
            return False

    def get_recovery_code_count(self, user_id: int) -> int:
        """
        Get the count of remaining (unused) recovery codes for a user.
        """
        try:
            with self.database_handler.connection() as db:
                cursor = db.execute(
                    """
                    SELECT COUNT(*) FROM RecoveryCodes
                    WHERE user_id = ? AND used_at IS NULL
                    """,
                    (user_id,)
                )
                row = cursor.fetchone()
                return row[0] if row else 0

        except Exception as e:
            logging.error(f"Error getting recovery code count: {e}")
            return 0

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        try:
            with self.database_handler.connection() as db:
                cursor = db.execute(
                    "SELECT id, username, email FROM Users WHERE id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    return {"id": row[0], "username": row[1], "email": row[2]}
                return None
        except Exception as e:
            logging.error(f"Error fetching user by ID: {e}")
            return None
