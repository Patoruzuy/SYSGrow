import importlib.util
import sys
from pathlib import Path
from unittest.mock import ANY, Mock

AUTH_SERVICE_PATH = Path(__file__).resolve().parents[3] / "app/services/application/auth_service.py"
AUTH_MODULE_NAME = "auth_service_regression_under_test"
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_auth_spec = importlib.util.spec_from_file_location(AUTH_MODULE_NAME, AUTH_SERVICE_PATH)
auth_service_module = importlib.util.module_from_spec(_auth_spec)
sys.modules[AUTH_MODULE_NAME] = auth_service_module
assert _auth_spec is not None and _auth_spec.loader is not None
_auth_spec.loader.exec_module(auth_service_module)
UserAuthManager = auth_service_module.UserAuthManager


def test_reset_password_with_token_fails_when_repo_atomic_write_fails():
    repo = Mock()
    repo.use_reset_token_and_update_password.return_value = False
    repo.update_password = Mock()
    repo.mark_token_used = Mock()

    audit_logger = Mock()
    manager = UserAuthManager(
        database_handler=Mock(),
        audit_logger=audit_logger,
        auth_repo=repo,
    )
    manager.validate_reset_token = Mock(return_value={"user_id": 7, "username": "alice", "token_id": 21})
    manager.hash_password = Mock(return_value="hashed-password")

    result = manager.reset_password_with_token("valid-token", "new-password")

    assert result is False
    repo.use_reset_token_and_update_password.assert_called_once_with(7, 21, "hashed-password", ANY)
    # Regression guard: no partial-write two-call flow when atomic path exists.
    repo.update_password.assert_not_called()
    repo.mark_token_used.assert_not_called()
    audit_logger.log_event.assert_any_call(
        actor="alice",
        action="password_reset",
        resource="user",
        outcome="error",
        error="write_failed",
    )


def test_generate_recovery_codes_returns_none_when_repo_persistence_fails():
    repo = Mock()
    repo.replace_recovery_codes.return_value = False

    audit_logger = Mock()
    manager = UserAuthManager(
        database_handler=Mock(),
        audit_logger=audit_logger,
        auth_repo=repo,
    )

    codes = manager.generate_recovery_codes(user_id=3)

    assert codes is None
    repo.replace_recovery_codes.assert_called_once()
    audit_logger.log_event.assert_any_call(
        actor="3",
        action="recovery_codes_generated",
        resource="user",
        outcome="error",
        error="write_failed",
    )


def test_auth_service_auto_initializes_repository_when_not_injected(monkeypatch):
    repo = Mock()
    repo.create_user.return_value = True
    repo.get_user_auth_by_username.return_value = {
        "id": 1,
        "username": "alice",
        "password_hash": "hashed-password",
        "email": "alice@example.com",
    }
    auth_repo_ctor = Mock(return_value=repo)
    monkeypatch.setattr(auth_service_module, "AuthRepository", auth_repo_ctor)

    manager = UserAuthManager(
        database_handler=object(),
        audit_logger=Mock(),
        auth_repo=None,
    )
    manager.hash_password = Mock(return_value="hashed-password")
    manager.check_password = Mock(return_value=True)

    assert manager.register_user("alice", "s3cret-pass") is True
    assert manager.authenticate_user("alice", "s3cret-pass") is True
    auth_repo_ctor.assert_called_once()
    repo.create_user.assert_called_once_with("alice", "hashed-password")
    repo.get_user_auth_by_username.assert_called_once_with("alice")
