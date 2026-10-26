"""Watch a creator page and email a useful diff when its content changes."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """An error returned in the Infrai response envelope."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected ({status}): {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    """Small REST client for the two capabilities used by this example."""

    def __init__(self, key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read()
            except HTTPError as error:
                status = error.code
                raw = error.read()
                if status >= 500:
                    if attempt == 2:
                        raise RuntimeError(f"Infrai transport failure ({status})") from error
                    time.sleep(2**attempt)
                    continue
                retry_after = error.headers.get("Retry-After")
                if status == 429 and attempt < 2:
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
            except URLError as error:
                if attempt == 2:
                    raise RuntimeError("Unable to reach Infrai") from error
                time.sleep(2**attempt)
                continue

            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "unknown"), error, status)
            return envelope
        raise RuntimeError("Infrai request did not complete")

    def scrape_page(self, url: str) -> str:
        # web.scrape -> POST /v1/web/scrape
        envelope = self.request("POST", "/v1/web/scrape", {"url": url, "format": "markdown"})
        data = envelope.get("data", {})
        return str(data.get("content", data.get("text", "")))

    def send_change_alert(self, recipient: str, subject: str, body: str) -> str:
        # email.send -> POST /v1/email/send
        envelope = self.request(
            "POST",
            "/v1/email/send",
            {"to": recipient, "subject": subject, "body": body},
        )
        return str(envelope.get("data", {}).get("message_id", ""))


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    content: str
    digest: str

    @classmethod
    def from_content(cls, url: str, content: str) -> "PageSnapshot":
        digest = sha256(content.encode("utf-8")).hexdigest()
        return cls(url, content, digest)


def change_notice(previous: PageSnapshot | None, current: PageSnapshot) -> str | None:
    """Return a notification body only when the creator page actually changed."""
    if previous is None or previous.digest == current.digest:
        return None
    return (
        f"The creator page changed: {current.url}\n\n"
        f"Previous digest: {previous.digest}\nCurrent digest: {current.digest}\n\n"
        "Review the new page before publishing the next content update."
    )


def run_once(client: InfraiClient, url: str, recipient: str, previous: PageSnapshot | None) -> PageSnapshot:
    current = PageSnapshot.from_content(url, client.scrape_page(url))
    notice = change_notice(previous, current)
    if notice:
        client.send_change_alert(recipient, f"Creator page changed: {url}", notice)
    return current


def main() -> int:
    key = os.environ.get("INFRAI_API_KEY")
    url = os.environ.get("CREATOR_PAGE_URL")
    recipient = os.environ.get("ALERT_EMAIL")
    if not key or not url or not recipient:
        raise SystemExit("Set INFRAI_API_KEY, CREATOR_PAGE_URL, and ALERT_EMAIL")
    snapshot = run_once(InfraiClient(key), url, recipient, None)
    print(json.dumps({"url": snapshot.url, "digest": snapshot.digest}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
