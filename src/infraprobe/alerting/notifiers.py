"""Alert notification backends.

Sends alerts via webhook (Slack/Teams/Discord compatible),
SMTP email, and local log file.
"""

import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any

import requests

from infraprobe.alerting.rules import Alert

logger = logging.getLogger("infraprobe.alerting.notifiers")


class WebhookNotifier:
    """Send alerts via HTTP webhook (Slack/Teams/Discord compatible)."""

    def __init__(self, url: str, timeout: int = 10) -> None:
        self.url = url
        self.timeout = timeout

    def send(self, alert: Alert) -> bool:
        """Send an alert to the webhook URL.

        Formats the payload in a Slack-compatible format that also
        works with Microsoft Teams and Discord incoming webhooks.

        Args:
            alert: The alert to send.

        Returns:
            True if the webhook accepted the payload.
        """
        severity_emoji = {
            "info": "info",
            "warning": "warning",
            "critical": "rotating_light",
        }
        emoji = severity_emoji.get(alert.severity, "bell")

        payload = {
            "text": f":{emoji}: *InfraProbe Alert*\n{alert.message}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*:{emoji}: {alert.severity.upper()}*\n"
                            f"*Rule:* {alert.rule_name}\n"
                            f"*Metric:* `{alert.metric}` = `{alert.current_value}`\n"
                            f"*Condition:* {alert.condition} (threshold: {alert.threshold})"
                        ),
                    },
                }
            ],
        }

        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code < 300:
                logger.info("Webhook alert sent successfully for %s", alert.rule_name)
                return True
            else:
                logger.error(
                    "Webhook returned %d for alert %s",
                    response.status_code,
                    alert.rule_name,
                )
                return False
        except requests.exceptions.RequestException as e:
            logger.error("Webhook notification failed: %s", e)
            return False


class EmailNotifier:
    """Send alerts via SMTP email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: list[str] | None = None,
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def send(self, alert: Alert) -> bool:
        """Send an alert email.

        Args:
            alert: The alert to send.

        Returns:
            True if the email was sent successfully.
        """
        subject = f"[InfraProbe {alert.severity.upper()}] {alert.rule_name}"
        body = (
            f"InfraProbe Alert\n"
            f"{'=' * 40}\n\n"
            f"Rule: {alert.rule_name}\n"
            f"Severity: {alert.severity}\n"
            f"Metric: {alert.metric}\n"
            f"Current Value: {alert.current_value}\n"
            f"Condition: {alert.condition}\n"
            f"Threshold: {alert.threshold}\n\n"
            f"Message: {alert.message}\n"
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            logger.info("Email alert sent for %s", alert.rule_name)
            return True
        except Exception as e:
            logger.error("Email notification failed: %s", e)
            return False


class LogNotifier:
    """Write alerts to a log file (always-on fallback)."""

    def send(self, alert: Alert) -> bool:
        """Log the alert using the standard logger.

        Args:
            alert: The alert to log.

        Returns:
            Always True.
        """
        logger.warning(
            "ALERT [%s] %s: %s = %s (%s)",
            alert.severity,
            alert.rule_name,
            alert.metric,
            alert.current_value,
            alert.condition,
        )
        return True


def create_notifier(notifier_type: str, config: dict[str, Any]) -> Any:
    """Factory function to create a notifier from config.

    Args:
        notifier_type: Type name ("webhook", "email", "log").
        config: Notifier-specific configuration dict.

    Returns:
        A notifier instance with a send() method.
    """
    if notifier_type == "webhook":
        return WebhookNotifier(url=config["url"], timeout=config.get("timeout", 10))
    elif notifier_type == "email":
        return EmailNotifier(**config)
    else:
        return LogNotifier()
