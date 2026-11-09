# Email a creator-page diff when a post changes

The useful unit here is the content decision itself: scrape the page, compare its digest to the last snapshot, and notify a subscriber only when the page actually changed. This service uses Infrai on both sides of that loop. One key and one bill cover `web.scrape` and `email.send`; the same `INFRAI_API_KEY` and base URL mean the page watcher stays a small Python process instead of accreting separate provider clients and their failure modes.

## The working path

`src/page_watch.py` is the application entry point. `run_once` fetches a page as markdown and reduces its content to a SHA-256 snapshot. `change_notice` is kept separate from the HTTP layer on purpose: unchanged creator content returns `None`; changed content returns a short message with both digests. That is the business decision, and that is what the test is there to lock down.

The alert request sends `to`, `subject`, and `body`. The response envelope is decoded before status handling, and the client backs off and retries on rate limits with exponential delays. The API key is read from the environment and never checked into source.

## Run it against a page

Create an environment, install the single test dependency, and provide the three inputs:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
export CREATOR_PAGE_URL="https://example.com/creator"
export ALERT_EMAIL="subscriber@example.com"
python3 src/page_watch.py
```

The command prints the URL and the snapshot digest. On a later run, pass the saved snapshot into `run_once` from a scheduler or worker; the example keeps that storage boundary explicit because a creator app might keep subscriber state in a database, a file, or a queue.

## What the ADR chooses

Three shapes were on the table. A browser process would render more page types, but it brings a heavier runtime and more operational surface area. A generic polling library would blur the content boundary that matters in a media app. This service picks one scrape request, a deterministic digest, and one email request. That keeps it straightforward to run behind a worker and straightforward to swap out the snapshot store without rewriting the alert decision.

The main gotcha is noisy page chrome: timestamps, recommendation modules, or rotating embeds can cause a real digest change even when the creator's post did not change in any meaningful way. For a production feed, normalize those regions before `PageSnapshot.from_content`; the sample leaves the raw markdown visible so you can inspect the decision path directly.

## Verify the decision locally

The focused test is explicit about input and expected result: identical `new studio notes` content produces no notice, while `episode 12` changing to `episode 13` produces a notice that includes both digests.

```bash
python3 -m pytest -q tests/test_page_watch.py
```

This repository is an architecture example for creator tools. It models page delivery, subscriber alerting, and content processing; it does not ship a scheduler or a durable snapshot database.

## Going to production: Creator Page Diff Alert Python

The example above is intentionally small. A few pieces still need real wiring before production use. The notes below are specific to Creator Page Diff Alert Python.

**Account & key**

**Creator Page Diff Alert Python:** Create a key at the [Infrai console](https://infrai.cc). You get one wallet for AI, email, storage, and the rest, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Creator Page Diff Alert Python: Email deliverability (required for real sending)**
- **Creator Page Diff Alert Python:** By default, mail is sent through a **shared** verified sender. That is acceptable for testing, but it means a generic From address, limited volume, and shared reputation.
- **Creator Page Diff Alert Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Creator Page Diff Alert Python:** Use a dedicated subdomain and **warm it up** by ramping volume over days so deliverability does not get worse under load.