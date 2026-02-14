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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from infrastructure.database.repositories.auth import AuthRepository
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
    # Optional injection for tests/composition; lazily initialized from database_handler.
    auth_repo: Optional[AuthRepository] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.auth_repo is None and self.database_handler is not None:
            self.auth_repo = AuthRepository(self.database_handler)

    def _repo(self) -> AuthRepository:
        if self.auth_repo is None:
            raise RuntimeError("AuthRepository is not configured")
        return self.auth_repo

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
            created = self._repo().create_user(username, password_hash)
            if not created:
                logging.error("Error registering user '%s': repository rejected create", username)
                if self.audit_logger:
                    self.audit_logger.log_event(
                        actor=username,
                        action="register",
                        resource="user",
                        outcome="error",
                        error="create_failed",
                    )
                return False
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
        user = self._repo().get_user_auth_by_username(username)
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
            return self._repo().get_user_by_email(email)
        except Exception as e:
            logging.error(f"Error fetching user by email: {e}")
            return None

    def get_user_by_username_with_email(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user with email by username."""
        try:
            return self._repo().get_user_by_username_with_email(username)
        except Exception as e:
            logging.error(f"Error fetching user by username: {e}")
            return None

    def update_user_email(self, user_id: int, email: str) -> bool:
        """Update user's email address."""
        try:
            result = self._repo().update_email(user_id, email)
            if result:
                logging.info(f"Updated email for user ID {user_id}")
            return result
        except Exception as e:
            logging.error(f"Error updating user email: {e}")
            return False

    def generate_reset_token(self, user_id: int) -> Optional[str]:
        """
        Generate a secure password reset token for a user.

        Returns the plain token (to be sent to user) - only the hash is stored.
        """
        try:
            token = secrets.token_hex(RESET_TOKEN_LENGTH)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires_at = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)

            ok = self._repo().create_reset_token(user_id, token_hash, expires_at.isoformat())
            if not ok:
                return None

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
            row = self._repo().find_reset_token(token_hash)

            if not row:
                logging.warning("Invalid password reset token attempted")
                return None

            used_at = row.get("used_at")
            username = row.get("username")
            expires_at_str = row.get("expires_at")

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
                "token_id": row.get("token_id"),
                "user_id": row.get("user_id"),
                "username": username,
                "email": row.get("email"),
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
            used_at = datetime.utcnow().isoformat()

            persisted = self._repo().use_reset_token_and_update_password(
                user_id,
                token_id,
                password_hash,
                used_at,
            )

            if not persisted:
                logging.error(f"Password reset failed for user '{username}': database write failed")
                if self.audit_logger:
                    self.audit_logger.log_event(
                        actor=username,
                        action="password_reset",
                        resource="user",
                        outcome="error",
                        error="write_failed",
                    )
                return False

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
            cutoff = datetime.utcnow().isoformat()
            deleted = self._repo().cleanup_expired_tokens(cutoff)

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

            created_at = datetime.utcnow().isoformat()

            persisted = self._repo().replace_recovery_codes(user_id, code_hashes, created_at)
            if not persisted:
                logging.error(f"Failed to persist recovery codes for user ID {user_id}")
                if self.audit_logger:
                    self.audit_logger.log_event(
                        actor=str(user_id),
                        action="recovery_codes_generated",
                        resource="user",
                        outcome="error",
                        error="write_failed",
                    )
                return None

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
            return self._repo().find_unused_recovery_code(user_id, code_hash) is not None

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
            password_hash = self.hash_password(new_password)

            ok = self._repo().use_recovery_code_and_reset_password(
                user_id=user_id,
                code_hash=code_hash,
                password_hash=password_hash,
                used_at_iso=datetime.utcnow().isoformat(),
            )
            if not ok:
                logging.warning(f"Invalid or used recovery code attempted for user ID {user_id}")
                return False

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
            return self._repo().count_unused_recovery_codes(user_id)

        except Exception as e:
            logging.error(f"Error getting recovery code count: {e}")
            return 0

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        try:
            return self._repo().get_user_by_id(user_id)
        except Exception as e:
            logging.error(f"Error fetching user by ID: {e}")
            return None
