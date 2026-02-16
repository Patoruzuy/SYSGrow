from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.security.auth import current_username

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login() -> str:
    if current_username():
        flash("You are already logged in.", "info")
        return redirect(url_for("ui.index"))
    return render_template("login.html")


@auth_bp.post("/login")
def authenticate():
    container = current_app.config["CONTAINER"]
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    remember_me = request.form.get("remember_me") == "on"

    # --- brute-force protection -------------------------------------------
    limiter = current_app.config.get("LOGIN_LIMITER")
    client_ip = request.remote_addr or "unknown"
    if limiter:
        locked, remaining = limiter.is_locked(client_ip)
        if locked:
            minutes_left = (remaining + 59) // 60  # round up
            flash(
                f"Too many failed attempts. Try again in {minutes_left} minute(s).",
                "error",
            )
            return redirect(url_for("auth.login"))

    if container.auth_manager.authenticate_user(username, password):
        # Clear brute-force counter on success
        if limiter:
            limiter.record_success(client_ip)
        # Security: Regenerate session to prevent session fixation attacks
        # Preserve selected_unit preference if it exists
        preserved_unit = session.get("selected_unit")
        session.clear()

        # Get the actual user_id from the database
        user_info = container.auth_manager.get_user_by_username_with_email(username)
        user_id = user_info["id"] if user_info else 1

        # Store user in session
        session["user"] = username
        session["user_id"] = user_id

        # Handle "Remember Me" - permanent session uses PERMANENT_SESSION_LIFETIME (30 days)
        # Non-permanent session expires when browser closes
        session["remember_me"] = remember_me
        session.permanent = remember_me

        # Restore preserved unit selection if it was set
        if preserved_unit is not None:
            session["selected_unit"] = preserved_unit

        # Auto-select first unit if no unit is selected (use "selected_unit" not "selected_unit_id")
        if "selected_unit" not in session or session["selected_unit"] is None:
            try:
                units = container.growth_service.list_units()
                if units and len(units) > 0:
                    first_unit_id = units[0].get("unit_id")
                    if first_unit_id:
                        session["selected_unit"] = first_unit_id
                        current_app.logger.info(f"✅ Auto-selected unit {first_unit_id} for user '{username}'")
            except Exception as e:
                current_app.logger.error(f"❌ Error auto-selecting unit for user '{username}': {e}")

        container.audit_logger.log_event(actor=username, action="login", resource="session", outcome="success")

        # Log activity
        from app.services.application.activity_logger import ActivityLogger

        if hasattr(container, "activity_logger") and container.activity_logger:
            container.activity_logger.log_activity(
                activity_type=ActivityLogger.USER_LOGIN,
                description=f"User '{username}' logged in",
                user_id=session.get("user_id"),
                severity=ActivityLogger.INFO,
            )

        flash("Logged in successfully!", "success")
        return redirect(url_for("ui.index"))

    container.audit_logger.log_event(
        actor=username or "anonymous", action="login", resource="session", outcome="denied"
    )

    # Record failed attempt for brute-force protection
    if limiter:
        now_locked, _ = limiter.record_failure(client_ip)
        if now_locked:
            flash(
                "Too many failed attempts. Your access has been temporarily locked.",
                "error",
            )
            return redirect(url_for("auth.login"))

    flash("Invalid username or password.", "error")
    return redirect(url_for("auth.login"))


@auth_bp.get("/register")
def register() -> str:
    return render_template("register.html")


@auth_bp.post("/register")
def process_registration():
    container = current_app.config["CONTAINER"]
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for("auth.register"))

    if container.auth_manager.register_user(username, password):
        container.audit_logger.log_event(actor=username, action="register", resource="user", outcome="success")

        # Create default growth unit for new user
        try:
            unit_id = container.growth_service.create_unit(
                name="My First Unit",
                location="Indoor",
                user_id=1,  # Default user ID
            )
            if unit_id:
                current_app.logger.info(f"✅ Created default unit (ID: {unit_id}) for new user '{username}'")
            else:
                current_app.logger.warning(f"⚠️ Failed to create default unit for user '{username}'")
        except Exception as e:
            current_app.logger.error(f"❌ Error creating default unit for user '{username}': {e}")

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    container.audit_logger.log_event(actor=username, action="register", resource="user", outcome="conflict")
    flash("Registration failed. Username might already exist.", "error")
    return redirect(url_for("auth.register"))


@auth_bp.get("/logout")
def logout():
    username = session.pop("user", None)
    user_id = session.pop("user_id", None)
    if username:
        container = current_app.config["CONTAINER"]
        container.audit_logger.log_event(actor=username, action="logout", resource="session", outcome="success")

        # Log activity
        from app.services.application.activity_logger import ActivityLogger

        if hasattr(container, "activity_logger") and container.activity_logger:
            container.activity_logger.log_activity(
                activity_type=ActivityLogger.USER_LOGOUT,
                description=f"User '{username}' logged out",
                user_id=user_id,
                severity=ActivityLogger.INFO,
            )

    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# --- Password Recovery Routes ---


@auth_bp.get("/forgot-password")
def forgot_password() -> str:
    """Display the forgot password form."""
    if current_username():
        flash("You are already logged in.", "info")
        return redirect(url_for("ui.index"))
    return render_template("forgot_password.html")


@auth_bp.post("/forgot-password")
def process_forgot_password():
    """Process forgot password request and send reset link."""
    container = current_app.config["CONTAINER"]
    identifier = request.form.get("identifier", "").strip()

    if not identifier:
        flash("Please enter your username or email address.", "error")
        return redirect(url_for("auth.forgot_password"))

    # Try to find user by email or username
    user = None
    if "@" in identifier:
        user = container.auth_manager.get_user_by_email(identifier)

    if not user:
        user = container.auth_manager.get_user_by_username_with_email(identifier)

    if not user:
        # Don't reveal if user exists - always show success message
        current_app.logger.warning(f"Password reset requested for unknown user: {identifier}")
        flash("If an account exists with that username or email, you will receive password reset instructions.", "info")
        return redirect(url_for("auth.login"))

    # Generate reset token
    token = container.auth_manager.generate_reset_token(user["id"])

    if not token:
        flash("An error occurred. Please try again later.", "error")
        return redirect(url_for("auth.forgot_password"))

    # Build reset URL
    reset_url = url_for("auth.reset_password", token=token, _external=True)

    # Try to send email if user has email configured
    email_sent = False
    if user.get("email"):
        try:
            email_service = getattr(container, "email_service", None)
            if email_service:
                from app.services.utilities.email_service import EmailMessage

                email_msg = EmailMessage(
                    to_address=user["email"],
                    subject="SYSGrow Password Reset",
                    body_text=f"""
Hello {user["username"]},

You requested a password reset for your SYSGrow account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this reset, please ignore this email.

---
SYSGrow Smart Agriculture Platform
                    """,
                    body_html=f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background-color: #2ecc71; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 30px; }}
        .btn {{ display: inline-block; padding: 12px 24px; background-color: #2ecc71; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }}
        .footer {{ padding: 15px 20px; background-color: #f9f9f9; font-size: 12px; color: #666; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Password Reset</h1>
        </div>
        <div class="content">
            <p>Hello <strong>{user["username"]}</strong>,</p>
            <p>You requested a password reset for your SYSGrow account.</p>
            <p>Click the button below to reset your password:</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="btn">Reset Password</a>
            </p>
            <p><small>This link will expire in 1 hour.</small></p>
            <p>If you did not request this reset, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>SYSGrow Smart Agriculture Platform</p>
        </div>
    </div>
</body>
</html>
                    """,
                )
                email_sent = email_service.send(email_msg)
        except Exception as e:
            current_app.logger.error(f"Failed to send password reset email: {e}")

    if email_sent:
        flash("Password reset instructions have been sent to your email.", "success")
    else:
        # If email not configured or failed, show the reset link directly
        # In production, you might want to handle this differently
        flash(f"Email not configured. Use this link to reset your password: {reset_url}", "warning")

    container.audit_logger.log_event(
        actor=user["username"],
        action="password_reset_request",
        resource="user",
        outcome="success" if email_sent else "no_email",
    )

    return redirect(url_for("auth.login"))


@auth_bp.get("/reset-password/<token>")
def reset_password(token: str) -> str:
    """Display the reset password form."""
    container = current_app.config["CONTAINER"]

    # Validate token before showing form
    token_info = container.auth_manager.validate_reset_token(token)

    if not token_info:
        flash("Invalid or expired reset link. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    return render_template("reset_password.html", token=token, username=token_info["username"])


@auth_bp.post("/reset-password/<token>")
def process_reset_password(token: str):
    """Process the password reset."""
    container = current_app.config["CONTAINER"]

    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not password:
        flash("Password is required.", "error")
        return redirect(url_for("auth.reset_password", token=token))

    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for("auth.reset_password", token=token))

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.reset_password", token=token))

    # Reset the password
    if container.auth_manager.reset_password_with_token(token, password):
        flash("Your password has been reset successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))
    else:
        flash("Failed to reset password. The link may have expired.", "error")
        return redirect(url_for("auth.forgot_password"))


# --- Recovery Code Routes (Offline Password Recovery) ---


@auth_bp.get("/recover")
def recover() -> str:
    """Display the recovery code password reset form."""
    if current_username():
        flash("You are already logged in.", "info")
        return redirect(url_for("ui.index"))
    return render_template("recover_account.html")


@auth_bp.post("/recover")
def process_recover():
    """Process password reset using a recovery code."""
    container = current_app.config["CONTAINER"]

    username = request.form.get("username", "").strip()
    recovery_code = request.form.get("recovery_code", "").strip()
    password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not username:
        flash("Username is required.", "error")
        return redirect(url_for("auth.recover"))

    if not recovery_code:
        flash("Recovery code is required.", "error")
        return redirect(url_for("auth.recover"))

    if not password:
        flash("New password is required.", "error")
        return redirect(url_for("auth.recover"))

    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "error")
        return redirect(url_for("auth.recover"))

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.recover"))

    # Find user by username
    user = container.auth_manager.get_user_by_username_with_email(username)
    if not user:
        # Don't reveal if user exists
        flash("Invalid username or recovery code.", "error")
        container.audit_logger.log_event(
            actor=username or "anonymous",
            action="recovery_code_attempt",
            resource="user",
            outcome="user_not_found",
        )
        return redirect(url_for("auth.recover"))

    user_id = user["id"]

    # Validate the recovery code
    if not container.auth_manager.validate_recovery_code(user_id, recovery_code):
        flash("Invalid username or recovery code.", "error")
        container.audit_logger.log_event(
            actor=username,
            action="recovery_code_attempt",
            resource="user",
            outcome="invalid_code",
        )
        return redirect(url_for("auth.recover"))

    # Reset the password
    if container.auth_manager.reset_password_with_recovery_code(user_id, recovery_code, password):
        flash("Your password has been reset successfully. Please log in.", "success")
        container.audit_logger.log_event(
            actor=username,
            action="password_reset_recovery",
            resource="user",
            outcome="success",
        )
        return redirect(url_for("auth.login"))
    else:
        flash("Failed to reset password. Please try again.", "error")
        return redirect(url_for("auth.recover"))
