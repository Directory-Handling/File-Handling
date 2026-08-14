from django.conf import settings
from django.db import models


class FileUpload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('uploaded', 'Uploaded'),
        ('scanning', 'Scanning'),      # ClamAV scan in progress
        ('clean', 'Clean'),            # passed scan, thumbnail may be pending
        ('rejected', 'Rejected'),      # magic-byte type mismatch
        ('infected', 'Infected'),      # failed ClamAV scan
        ('failed', 'Failed'),          # transient error (S3/ClamAV unreachable)
        ('ready', 'Ready'),
    ]

    key = models.CharField(max_length=500, unique=True)
    thumbnail_key = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    checksum = models.CharField(max_length=64, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.file_name or self.key} ({self.status})"
