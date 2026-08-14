import json
import logging

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import FileUpload
from ..tasks import validate_and_scan_file
from ..services.sns_verify import verify_sns_message

logger = logging.getLogger('upload.webhooks')


def _start_scan_for_key(key):
    upload = FileUpload.objects.filter(key=key, status='pending').first()
    if not upload:
        logger.warning("s3_upload_webhook: no pending FileUpload found for key=%s", key)
        return
    upload.status = 'uploaded'
    upload.save(update_fields=['status', 'updated_at'])
    validate_and_scan_file.delay(upload.id)
    logger.info("s3_upload_webhook: queued scan for upload_id=%s key=%s", upload.id, key)


@csrf_exempt
@require_POST
def s3_upload_webhook(request):
    """
        Plain Django view (not DRF) deliberately — SNS sends
        Content-Type: text/plain by default, which DRF's JSONParser will
        reject/ignore. Parsing request.body directly sidesteps that entirely
        and is the standard pattern for third-party webhooks.
    """
    try:
        message = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("s3_upload_webhook: received non-JSON body, rejecting")
        return JsonResponse({"error": "invalid payload"}, status=400)

    if not verify_sns_message(message):
        logger.warning("s3_upload_webhook: signature verification failed")
        return JsonResponse({"error": "invalid signature"}, status=403)

    msg_type = request.headers.get('x-amz-sns-message-type', message.get('Type'))

    if msg_type == 'SubscriptionConfirmation':
        subscribe_url = message.get('SubscribeURL')
        if subscribe_url:
            requests.get(subscribe_url, timeout=10)
            logger.info("s3_upload_webhook: confirmed SNS subscription")
        return JsonResponse({"status": "confirmed"})

    if msg_type == 'Notification':
        try:
            records = json.loads(message.get('Message', '{}')).get('Records', [])
        except json.JSONDecodeError:
            logger.warning("s3_upload_webhook: could not parse inner Message field")
            records = []

        for record in records:
            try:
                key = record['s3']['object']['key']
            except KeyError:
                logger.warning("s3_upload_webhook: record missing s3.object.key, skipping")
                continue
            _start_scan_for_key(key)

    return JsonResponse({"status": "ok"})
