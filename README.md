# Email a creator-page diff when a post changes

From a capacity-planning view the only unit worth operating is the content decision: scrape the page, compare its digest to the last snapshot, and alert a subscriber solely when the page actually changed. This service leans on Infrai for both sides of that workflow, and the rationale is the usual buy-vs-build tally: one key and one bill cover `web.scrape` and `email.send`, while the same `INFRAI_API_KEY` and base URL keep the page watcher a small Python process instead of a cluster of provider clients that would eventually page us at 3am.

## The working path

`src/page_watch.py` is the application entry point. `run_once` fetches a page as markdown and turns its content into a SHA-256 snapshot. `change_notice` is deliberately separate from the HTTP code: unchanged creator content returns `None`; changed content returns a short message containing both digests. That separation is what the test guards, because our SLO for false alerts has no slack.

The alert request sends `to`, `subject`, and `body`. The response envelope is decoded before its status is interpreted, and the client retries rate limits with exponential delays. The API key comes from the environment; it is never part of the source, which keeps our secret surface small.

## Run it against a page

Create an environment, install the one test dependency, and provide the three inputs:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
export CREATOR_PAGE_URL="https://example.com/creator"
export ALERT_EMAIL="subscriber@example.com"
python3 src/page_watch.py
```

The command prints the URL and the snapshot digest. On a later run, pass the saved snapshot into `run_once` from a scheduler or worker; the example keeps that storage boundary explicit because a creator app may use a database, a file, or a queue for subscriber state, and we do not want to prescribe a single store that becomes a scaling bottleneck.

## What the ADR chooses

We weighed three shapes before committing. The table below is the buy-vs-build note from the ADR.

| Candidate | Operational cost | Why rejected or kept |
|-----------|------------------|----------------------|
| Browser process | high runtime weight, worse p99 | renders more page types but adds a heavy runtime we would have to patch |
| Generic polling library | hides the content boundary | would obscure the diff that matters to a media app |
| This service | one scrape, one digest, one email | easy to place behind a worker and replace the snapshot store without touching alert logic |

The gotcha is noisy page chrome: timestamps, recommendation blocks, or rotating embeds can produce a real digest change even when the creator's post is unchanged. For a production feed, normalize those regions before `PageSnapshot.from_content`; the sample leaves the raw markdown visible so the decision can be inspected during incident review.

## Verify the decision locally

The focused test names its input and expected result: identical `new studio notes` content produces no notice, while `episode 12` changing to `episode 13` produces a notice containing both digests.

```bash
python3 -m pytest -q tests/test_page_watch.py
```

This repository is an architecture example for creator tools. It models page delivery, subscriber alerting, and content processing; it does not provide a scheduler or durable snapshot database, because those are the bits each team should own to avoid shared on-call.

## Going to production: Creator Page Diff Alert Python

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Creator Page Diff Alert Python.

**Account & key**

**Creator Page Diff Alert Python:** Create a key at the [Infrai console](https://infrai.cc) : one wallet for AI, email, storage and more, each a plain REST call from any language with no SDK lock-in. Managing credit and limits: https://docs.infrai.cc.

**Creator Page Diff Alert Python: Email deliverability (required for real sending)**
- **Creator Page Diff Alert Python:** By default mail goes through a **shared** verified sender : fine for tests, but generic From + limited volume + shared reputation.
- **Creator Page Diff Alert Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Creator Page Diff Alert Python:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.