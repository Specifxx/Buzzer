"""Operator notifications for the daily scan.

The default channel is a GitHub issue in this repository — free, keeps
an audit trail, and GitHub already pings phone/email. The transport is
the same injectable protocol as the Printify client, so tests assert
the exact payload without any network.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

from buzzer.publish.printify import PrintifyError, TransportLike, _default_transport

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class Notifier(Protocol):
    def notify(self, subject: str, body: str) -> None: ...


class LogNotifier:
    """Fallback: write the notification to the log/console."""

    def notify(self, subject: str, body: str) -> None:
        logger.info("NOTIFICATION: %s\n%s", subject, body)


class GitHubIssueNotifier:
    """Open a GitHub issue (label: buzzer-approval) as the notification."""

    def __init__(self, repo: str, token: str, transport: TransportLike | None = None) -> None:
        self.repo = repo
        self._token = token
        self.transport = transport if transport is not None else _default_transport()

    def notify(self, subject: str, body: str) -> None:
        response = self.transport.request(
            "POST",
            f"{GITHUB_API}/repos/{self.repo}/issues",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "buzzer-poster-pipeline",
            },
            json={"title": subject, "body": body, "labels": ["buzzer-approval"]},
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise PrintifyError(
                f"GitHub issue creation failed: {response.status_code}: {response.text}"
            )
        logger.info("notification issue created: %s", response.json().get("html_url", ""))


def build_notifier(channel: str, transport: TransportLike | None = None) -> Notifier:
    """``github`` needs GITHUB_TOKEN and BUZZER_NOTIFY_REPO/GITHUB_REPOSITORY."""
    if channel == "github":
        token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("BUZZER_NOTIFY_REPO") or os.environ.get("GITHUB_REPOSITORY", "")
        if token and repo:
            return GitHubIssueNotifier(repo=repo, token=token, transport=transport)
        logger.warning(
            "github notifier requested but GITHUB_TOKEN/BUZZER_NOTIFY_REPO missing; "
            "falling back to log output"
        )
    return LogNotifier()
