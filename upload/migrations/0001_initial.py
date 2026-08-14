from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FileUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=500, unique=True)),
                ('thumbnail_key', models.CharField(blank=True, max_length=500, null=True)),
                ('status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('uploaded', 'Uploaded'),
                    ('scanning', 'Scanning'),
                    ('clean', 'Clean'),
                    ('rejected', 'Rejected'),
                    ('infected', 'Infected'),
                    ('failed', 'Failed'),
                    ('ready', 'Ready'),
                ], default='pending', max_length=20)),
                ('checksum', models.CharField(blank=True, max_length=64)),
                ('file_name', models.CharField(blank=True, max_length=255)),
                ('content_type', models.CharField(blank=True, max_length=100)),
                ('size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='uploads', to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.AddIndex(
            model_name='fileupload',
            index=models.Index(fields=['key'], name='upload_file_key_idx'),
        ),
        migrations.AddIndex(
            model_name='fileupload',
            index=models.Index(fields=['status', 'created_at'], name='upload_file_status_idx'),
        ),
    ]
