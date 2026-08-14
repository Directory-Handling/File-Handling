from django.urls import path

from .views.presigned import get_presigned_url
from .views.webhooks import s3_upload_webhook
from .views.download import get_download_url, get_upload_status

urlpatterns = [
    path('presigned-url/', get_presigned_url, name='get-presigned-url'),
    path('webhooks/s3-upload/', s3_upload_webhook, name='s3-upload-webhook'),
    path('uploads/<int:upload_id>/status/', get_upload_status, name='upload-status'),
    path('uploads/<int:upload_id>/download-url/', get_download_url, name='download-url'),
]
