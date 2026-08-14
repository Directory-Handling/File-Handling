from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from ..models import FileUpload
from ..serializers import PresignedUrlRequestSerializer
from ..services import s3_service

# | Class                | Limits based on | Typical use                   |
# | -------------------- | --------------- | ----------------------------- |
# | `AnonRateThrottle`   | IP address      | Anonymous APIs                |
# | `UserRateThrottle`   | User            | Logged-in users               |
# | `ScopedRateThrottle` | API scope       | Different limits per endpoint |
# | `SimpleRateThrottle` | Custom          | Build your own throttle       |

class UploadRateThrottle(AnonRateThrottle):
    scope = 'uploads'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def get_presigned_url(request):
    serializer = PresignedUrlRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    key = s3_service.build_object_key(data['file_name'])

    presigned_post = s3_service.generate_presigned_post(
        key=key,
        content_type=data['file_type'],
        max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
    )

    upload = FileUpload.objects.create(
        key=key,
        status='pending',
        file_name=data['file_name'],
        content_type=data['file_type'],
        size_bytes=data['file_size'],
        checksum=data.get('checksum', '')
    )

    return Response({
        "upload_id": upload.id,
        "upload_post": presigned_post,
    })
