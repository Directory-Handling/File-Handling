import hashlib
import io
import logging
from datetime import timedelta

import magic
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import FileUpload
from .services import s3_service
from .services.clamav_service import run_clamav_scan

logger = logging.getLogger('upload.tasks')

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
STUCK_THRESHOLD_MINUTES = 30


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def validate_and_scan_file(self, upload_id):
    try:
        upload = FileUpload.objects.get(id=upload_id)
    except FileUpload.DoesNotExist:
        logger.warning("validate_and_scan_file: upload_id=%s does not exist", upload_id)
        return

    # already processed — avoid duplicate work if triggered twice
    # (e.g. both webhook and reconciliation job fired)
    if upload.status not in ('pending', 'uploaded'):
        logger.info(
            "validate_and_scan_file: upload_id=%s already in status=%s, skipping",
            upload_id, upload.status,
        )
        return

    if not s3_service.object_exists(upload.key):
        logger.error("validate_and_scan_file: object missing in S3 for upload_id=%s key=%s", upload_id, upload.key)
        upload.status = 'failed'
        upload.save(update_fields=['status', 'updated_at'])
        return

    file_head = s3_service.get_object_head_bytes(upload.key)
    detected_type = magic.from_buffer(file_head, mime=True)

    if detected_type not in settings.ALLOWED_MIME_TYPES:
        logger.warning(
            "validate_and_scan_file: upload_id=%s rejected, detected_type=%s not allowed",
            upload_id, detected_type,
        )
        upload.status = 'rejected'
        upload.save(update_fields=['status', 'updated_at'])
        s3_service.delete_object(upload.key)
        return

    # Optional integrity check — only runs if the client supplied a checksum
    # at presign time. Mismatch means the uploaded bytes differ from what
    # the client claimed to send (corruption or tampering in transit).
    if upload.checksum:
        actual_hash = hashlib.sha256(s3_service.get_object_bytes(upload.key)).hexdigest()
        if actual_hash != upload.checksum:
            logger.warning(
                "validate_and_scan_file: upload_id=%s checksum mismatch (expected=%s actual=%s)",
                upload_id, upload.checksum, actual_hash,
            )
            upload.status = 'rejected'
            upload.save(update_fields=['status', 'updated_at'])
            s3_service.delete_object(upload.key)
            return

    upload.status = 'scanning'
    upload.save(update_fields=['status', 'updated_at'])
    logger.info("validate_and_scan_file: upload_id=%s scanning started", upload_id)

    try:
        scan_result = run_clamav_scan(upload.key)
    except Exception as exc:
        logger.error("validate_and_scan_file: upload_id=%s scan infra error: %s (retry %s/%s)",
                     upload_id, exc, self.request.retries, self.max_retries)
        raise self.retry(exc=exc)

    if scan_result.is_clean:
        upload.status = 'clean'
        upload.save(update_fields=['status', 'updated_at'])
        logger.info("validate_and_scan_file: upload_id=%s clean, queuing thumbnail", upload_id)
        generate_thumbnail.delay(upload.id)
    else:
        logger.warning("validate_and_scan_file: upload_id=%s infected (%s)", upload_id, scan_result.detail)
        upload.status = 'infected'
        upload.save(update_fields=['status', 'updated_at'])
        s3_service.delete_object(upload.key)


@shared_task
def generate_thumbnail(upload_id):
    try:
        upload = FileUpload.objects.get(id=upload_id)
    except FileUpload.DoesNotExist:
        logger.warning("generate_thumbnail: upload_id=%s does not exist", upload_id)
        return

    if not upload.key.lower().endswith(IMAGE_EXTENSIONS):
        upload.status = 'ready'
        upload.save(update_fields=['status', 'updated_at'])
        return

    try:
        from PIL import Image

        image_data = s3_service.get_object_bytes(upload.key)
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((300, 300))

        buffer = io.BytesIO()
        img_format = img.format or 'JPEG'
        img.save(buffer, format=img_format)
        buffer.seek(0)

        thumb_key = upload.key.rsplit('.', 1)[0] + '_thumb.' + img_format.lower()
        s3_service.put_object(thumb_key, buffer, f'image/{img_format.lower()}')

        upload.thumbnail_key = thumb_key
        upload.status = 'ready'
        upload.save(update_fields=['thumbnail_key', 'status', 'updated_at'])
        logger.info("generate_thumbnail: upload_id=%s thumbnail created at %s", upload_id, thumb_key)
    except Exception:
        # thumbnail is a nice-to-have — don't strand an already-clean file
        logger.exception("generate_thumbnail: upload_id=%s failed, marking ready anyway", upload_id)
        upload.status = 'ready'
        upload.save(update_fields=['status', 'updated_at'])


@shared_task
def reconcile_stuck_uploads():
    """
    Safety net for the SNS webhook. Run on a schedule (Celery Beat, e.g.
    every 10 minutes). Sweeps uploads stuck in pending/uploaded past a
    threshold and either re-triggers the scan (object exists but the
    webhook never fired) or marks them failed + cleans up (object never
    showed up — abandoned upload).
    """
    cutoff = timezone.now() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
    stuck = FileUpload.objects.filter(status__in=['pending', 'uploaded'], created_at__lt=cutoff)

    count = stuck.count()
    if count:
        logger.info("reconcile_stuck_uploads: found %s stuck upload(s)", count)

    for upload in stuck:
        if s3_service.object_exists(upload.key):
            logger.info("reconcile_stuck_uploads: re-triggering scan for upload_id=%s", upload.id)
            validate_and_scan_file.delay(upload.id)
        else:
            logger.warning("reconcile_stuck_uploads: upload_id=%s abandoned, marking failed", upload.id)
            upload.status = 'failed'
            upload.save(update_fields=['status', 'updated_at'])
