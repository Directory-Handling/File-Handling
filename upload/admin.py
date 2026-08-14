from django.contrib import admin

from .models import FileUpload


@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_name', 'status', 'size_bytes', 'created_at')
    list_filter = ('status', 'content_type')
    search_fields = ('file_name', 'key')
    readonly_fields = ('key', 'thumbnail_key', 'checksum', 'created_at', 'updated_at')
    ordering = ('-created_at',)
