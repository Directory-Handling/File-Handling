from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import FileUpload
from ..serializers import FileUploadStatusSerializer
from ..services import s3_service


@api_view(['GET'])
@permission_classes([AllowAny])
def get_upload_status(request, upload_id):
    upload = FileUpload.objects.filter(id=upload_id).first()
    if not upload:
        return Response({"error": "not found"}, status=404)
    return Response(FileUploadStatusSerializer(upload).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_download_url(request, upload_id):
    upload = FileUpload.objects.filter(id=upload_id).first()
    if not upload:
        return Response({"error": "not found"}, status=404)

    if upload.status != 'ready':
        return Response({"error": f"file not ready (status={upload.status})"}, status=400)

    url = s3_service.generate_presigned_get(upload.key)

    thumbnail_url = (
        s3_service.generate_presigned_get(upload.thumbnail_key)
        if upload.thumbnail_key else None
    )

    return Response({"url": url, "thumbnail_url": thumbnail_url})
