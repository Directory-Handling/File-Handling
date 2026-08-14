from django.conf import settings
from rest_framework import serializers

from .models import FileUpload


class PresignedUrlRequestSerializer(serializers.Serializer):
    file_name = serializers.CharField(max_length=255)
    file_type = serializers.CharField(max_length=100)
    file_size = serializers.IntegerField(min_value=1)
    # Optional client-computed SHA-256 (hex digest, 64 chars) for
    # integrity verification. If provided, the scan task checks the
    # uploaded object's real hash against this after upload completes.
    checksum = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate_checksum(self, value):
        if value and (len(value) != 64 or not all(c in '0123456789abcdef' for c in value.lower())):
            raise serializers.ValidationError("checksum must be a 64-character hex SHA-256 digest.")
        return value.lower() if value else value

    def validate_file_type(self, value):
        if value not in settings.ALLOWED_MIME_TYPES:
            raise serializers.ValidationError(f"Content type '{value}' is not allowed.")
        return value

    def validate_file_size(self, value):
        if value > settings.MAX_UPLOAD_SIZE_BYTES:
            raise serializers.ValidationError(
                f"File exceeds max allowed size of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
            )
        return value


class FileUploadStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = ['id', 'file_name', 'status', 'created_at', 'updated_at']
