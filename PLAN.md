# File Upload System — Production Plan

## Architecture

```
Client                Django Backend                 AWS
------                ---------------                ---
POST /presigned-url/  → create FileUpload(pending)
                       → generate_presigned_post()
                                                       S3 bucket
Client POST file  ───────────────────────────────→   (direct upload,
                                                        Django never
                                                        touches bytes)

                                                       S3 ObjectCreated
                                                       → SNS topic
SNS POST ──────────→  /webhooks/s3-upload/
                       → find FileUpload by key
                       → status = 'uploaded'
                       → validate_and_scan_file.delay()

Celery worker          validate_and_scan_file
                       → magic-byte check (reject if mismatched)
                       → ClamAV scan (delete if infected)
                       → status = 'clean' → generate_thumbnail.delay()
                       → status = 'ready'

Celery Beat            reconcile_stuck_uploads (every 10 min)
                       → sweep pending/uploaded records older than 30 min
                       → verify against S3 head_object
                       → re-trigger scan OR mark failed + cleanup

Client                 GET /download-url/<id>/
                       → ownership check + status == 'ready'
                       → signed, expiring download URL
```

## Why webhook-first, not client-triggered

The client-called `confirm-upload` endpoint from earlier dev/testing is now
**removed** in favor of two backend-owned triggers:

1. **SNS webhook** (`s3_upload_webhook`) — primary trigger. Fires only when
   S3 actually has the object. Doesn't depend on the client being honest,
   online, or even alive after the upload finishes.
2. **Reconciliation Celery Beat task** — safety net. Catches any upload that
   somehow never got picked up (SNS delivery failure, webhook downtime) by
   periodically checking `pending`/`uploaded` records directly against S3.

This means the backend is fully in control of state transitions — the
client's only two calls are "give me a presigned URL" and "give me a
download URL." Everything else is server-driven.

## File map

```
config/
  __init__.py                   wires the Celery app into Django on startup
  celery.py                     Celery app bootstrap
  settings_additions.py         Settings block to merge into your settings.py
upload/
  __init__.py
  apps.py                       Django AppConfig
  admin.py                      Admin site registration for FileUpload
  models.py                     FileUpload model + status choices
  serializers.py                DRF serializers (request validation)
  tasks.py                      Celery tasks: scan, thumbnail, reconcile
  urls.py
  migrations/__init__.py        (run makemigrations to populate this)
  services/
    __init__.py
    s3_service.py                boto3 client + S3 helper functions
    clamav_service.py            ClamAV scan wrapper
    sns_verify.py                Self-contained SNS signature verification
  views/
    __init__.py
    presigned.py                 POST /presigned-url/
    webhooks.py                  POST /webhooks/s3-upload/  (SNS)
    download.py                  GET  /uploads/<id>/download-url/, /status/
requirements.txt
```

## How to run this

This is now a **complete, standalone Django project** — `manage.py`,
`config/settings.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`
are all real and wired together. See `README.md` for the quickstart.

If you're merging this into a **different, already-existing** Django
project instead of running it standalone: copy the `upload/` app folder
over as-is, but merge the *contents* of this project's `config/settings.py`
(everything under "Upload / scan pipeline settings") into your own
`settings.py` rather than overwriting it — don't copy `config/` wholesale
onto an existing project, since that would clobber your real settings.

## Setup steps (in order)

1. `pip install -r requirements.txt`
2. `brew install libmagic clamav` (macOS) — scanning deps
3. Complete the "drop this into an existing project" steps above
4. `python manage.py makemigrations upload && python manage.py migrate`
5. Run Redis: `redis-server`
6. Run Celery worker: `celery -A config worker --loglevel=info`
7. Run Celery Beat (for reconciliation): `celery -A config beat --loglevel=info`
8. Create the SNS topic, bucket notification, and subscription (see
   `services/s3_service.py` docstring for the AWS CLI commands)
9. Point the SNS subscription at your real HTTPS endpoint (production
   domain, or ngrok tunnel for staging tests)

## Production hardening included
- SNS signature verification on the webhook, implemented directly (no
  abandoned third-party dependency), fetched certs restricted to
  `*.amazonaws.com`, and any verification failure safely rejects rather
  than crashing the endpoint with a 500
- Webhook parses `request.body` directly instead of relying on DRF's
  content-type-based parsing — SNS sends `text/plain`, which would
  otherwise silently fail to parse
- Ownership + status checks on download (mismatched owner returns 404,
  not 403, so file existence isn't leaked)
- DRF rate limiting (per-user upload throttle)
- Retry-with-backoff on transient scan failures
- Infected/rejected files deleted from S3 immediately
- Optional SHA-256 checksum verification (client-supplied at presign time,
  checked against the real uploaded bytes after upload)
- Reconciliation job so nothing gets silently stuck forever
- All S3/ClamAV calls wrapped — no unhandled crashes reach the worker log
- Structured logging across every task and view (`upload.*` loggers)
- Least-privilege IAM policy (`config/iam_policy.json`) scoped to the
  `uploads/` prefix only, not the whole bucket
- ClamAV supports both local-socket (dev) and network-socket
  (containerized/production) modes via `CLAMAV_MODE`
- Dockerfile + docker-compose wiring web/worker/beat/redis/clamav together
  for a reproducible deployment
- CORS guidance for both Django and the S3 bucket itself (two separate
  CORS configs are needed — easy to miss one)

## Known remaining gaps — be aware of these before calling this "done"
- **Not yet run against real infra.** Every piece has been reasoned
  through and unit-tested with mocks, but nothing has executed against a
  real S3 bucket, real ClamAV daemon, or real SNS topic. Treat the first
  real end-to-end run as a debugging session, not a formality.
- **No push notification to the client** when processing finishes — only
  polling (`/uploads/<id>/status/`) is implemented. A websocket/SSE layer
  would need to be added for real-time UI updates.
- **No error tracking service wired in** — Sentry integration is
  commented out in `settings_additions.py`, not connected to a real DSN.
- **`config/test_settings.py` is a minimal standalone settings module**,
  not your real project's settings — it exists purely so this app's test
  suite is runnable independent of your host project. Don't deploy with it.
- **The initial migration was hand-written**, not generated by
  `makemigrations` (no environment access to run it here). Regenerate it
  for real once this is dropped into your actual project and confirm it
  matches — treat the included one as a correct-by-inspection starting
  point, not a guarantee.

## Running the test suite
```bash
pip install -r requirements.txt
pytest
```
Covers: SNS signature verification (including the untrusted-cert-host and
malformed-signature cases), webhook payload parsing (including the
`text/plain` content-type SNS actually sends), the full scan task state
machine (missing object, disallowed type, checksum mismatch, clean,
infected, already-processed skip guard), the reconciliation sweep, and
view-level auth/ownership/validation checks.
