"""
Email Service
=============

Dedicated email sending service for SYSGrow platform.
Handles SMTP email delivery with HTML and plain text support.

Extracted from NotificationsService for:
- Single responsibility (email delivery only)
- Reusability across services
- Easier testing and mocking

Author: SYSGrow Team
Date: January 2026
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Configuration for email sending."""

    smtp_host: str
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    from_address: str | None = None

    @property
    def sender(self) -> str:
        """Get the sender address."""
        return self.from_address or self.smtp_username or "sysgrow@localhost"


@dataclass
class EmailMessage:
    """Represents an email message."""

    to_address: str
    subject: str
    body_text: str
    body_html: str | None = None

    def to_mime(self, from_address: str) -> MIMEMultipart:
        """Convert to MIME message."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = self.subject
        msg["From"] = from_address
        msg["To"] = self.to_address

        msg.attach(MIMEText(self.body_text, "plain"))
        if self.body_html:
            msg.attach(MIMEText(self.body_html, "html"))

        return msg


class EmailService:
    """
    Email sending service.

    Provides a clean interface for sending emails via SMTP.
    Supports TLS encryption and HTML content.
    """

    def __init__(self, config: EmailConfig | None = None):
        """
        Initialize EmailService.

        Args:
            config: Optional default email configuration.
                    Can be overridden per-send call.
        """
        self._default_config = config

    def send(
        self,
        message: EmailMessage,
        config: EmailConfig | None = None,
    ) -> bool:
        """
        Send an email message.

        Args:
            message: The email message to send.
            config: Optional config override (uses default if not provided).

        Returns:
            True if email was sent successfully, False otherwise.
        """
        cfg = config or self._default_config
        if not cfg:
            logger.error("No email configuration provided")
            return False

        if not cfg.smtp_host:
            logger.error("SMTP host not configured")
            return False

        try:
            mime_msg = message.to_mime(cfg.sender)

            if cfg.smtp_use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                    server.starttls(context=context)
                    if cfg.smtp_username and cfg.smtp_password:
                        server.login(cfg.smtp_username, cfg.smtp_password)
                    server.sendmail(cfg.sender, message.to_address, mime_msg.as_string())
            else:
                with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                    if cfg.smtp_username and cfg.smtp_password:
                        server.login(cfg.smtp_username, cfg.smtp_password)
                    server.sendmail(cfg.sender, message.to_address, mime_msg.as_string())

            logger.info(f"Email sent to {message.to_address}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_notification_email(
        self,
        to_address: str,
        title: str,
        message: str,
        severity: str,
        config: EmailConfig | None = None,
    ) -> bool:
        """
        Send a formatted notification email.

        Convenience method that builds HTML notification template.

        Args:
            to_address: Recipient email address.
            title: Notification title.
            message: Notification message.
            severity: Severity level (info, warning, critical).
            config: Optional config override.

        Returns:
            True if email was sent successfully.
        """
        # Plain text version
        text_content = f"""
SYSGrow Notification
--------------------

{title}

{message}

Severity: {severity.upper()}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---
This is an automated notification from your SYSGrow system.
        """

        # HTML version with styling
        severity_colors = {
            "info": "#3498db",
            "warning": "#f39c12",
            "critical": "#e74c3c",
        }
        color = severity_colors.get(severity.lower(), "#3498db")

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background-color: {color}; color: white; padding: 20px; }}
        .header h1 {{ margin: 0; font-size: 18px; }}
        .content {{ padding: 20px; }}
        .message {{ font-size: 16px; line-height: 1.6; color: #333; }}
        .footer {{ padding: 15px 20px; background-color: #f9f9f9; font-size: 12px; color: #666; }}
        .severity {{ display: inline-block; padding: 4px 8px; border-radius: 4px; background-color: {color}; color: white; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SYSGrow Notification</h1>
        </div>
        <div class="content">
            <h2>{title}</h2>
            <p class="message">{message}</p>
            <p><span class="severity">{severity.upper()}</span></p>
        </div>
        <div class="footer">
            <p>This is an automated notification from your SYSGrow smart agriculture system.</p>
            <p>Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>
        """

        email_msg = EmailMessage(
            to_address=to_address,
            subject=f"[SYSGrow {severity.upper()}] {title}",
            body_text=text_content,
            body_html=html_content,
        )

        return self.send(email_msg, config)
