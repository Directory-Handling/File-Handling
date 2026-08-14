# File Upload System

A complete, runnable Django project implementing a secure file upload
pipeline: presigned S3 uploads, content-based validation, ClamAV scanning,
and a backend-driven (SNS webhook + reconciliation) processing pipeline.

See `PLAN.md` for the full architecture, design rationale, and known gaps.

## Quickstart (local development)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# macOS scanning deps
brew install libmagic clamav

cp .env.example .env               # fill in your real AWS values

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/

python manage.py runserver
```

In separate terminals:
```bash
redis-server
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info     # for the reconciliation sweep
```

## Quickstart (Docker)

```bash
cp .env.example .env               # fill in your real AWS values
docker compose up --build
```

This brings up Django, the Celery worker, Celery beat, Redis, and ClamAV
together — no local Python/Redis/ClamAV installation needed.

## Running tests

```bash
pytest
```

Uses `config/test_settings.py` (an isolated in-memory SQLite settings
module) so the suite runs independently of your `.env`/real database.

## What you still need to configure yourself (can't be done from code)

- A real S3 bucket, with the `uploads/` prefix and CORS policy set
- An SNS topic subscribed to your deployed `/webhooks/s3-upload/` URL
  (see `upload/services/s3_service.py`'s docstring for the exact AWS CLI
  commands, or the AWS Console click-path covered earlier)
- IAM credentials/role with the permissions in `config/iam_policy.json`
- A real `DJANGO_SECRET_KEY` in production (`.env`), never the dev default
