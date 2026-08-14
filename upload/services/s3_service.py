"""
S3 helper functions — single shared boto3 client for the whole app.

--- One-time AWS setup for the SNS webhook trigger ---

1. Create the SNS topic:
   aws sns create-topic --name file-upload-notifications

2. Allow S3 to publish to it:
   aws sns set-topic-attributes \
     --topic-arn arn:aws:sns:REGION:ACCOUNT_ID:file-upload-notifications \
     --attribute-name Policy \
     --attribute-value '{
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Principal": {"Service": "s3.amazonaws.com"},
         "Action": "SNS:Publish",
         "Resource": "arn:aws:sns:REGION:ACCOUNT_ID:file-upload-notifications",
         "Condition": {"ArnLike": {"aws:SourceArn": "arn:aws:s3:::YOUR_BUCKET"}}
       }]
     }'

3. Tell the bucket to notify that topic on upload:
   aws s3api put-bucket-notification-configuration \
     --bucket YOUR_BUCKET \
     --notification-configuration '{
       "TopicConfigurations": [{
         "TopicArn": "arn:aws:sns:REGION:ACCOUNT_ID:file-upload-notifications",
         "Events": ["s3:ObjectCreated:*"],
         "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "uploads/"}]}}
       }]
     }'

4. Subscribe your production HTTPS endpoint:
   aws sns subscribe \
     --topic-arn arn:aws:sns:REGION:ACCOUNT_ID:file-upload-notifications \
     --protocol https \
     --notification-endpoint https://api.yourdomain.com/webhooks/s3-upload/
"""
import uuid

import boto3
from django.conf import settings

s3_client = boto3.client('s3', region_name=settings.AWS_REGION)


def build_object_key(file_name: str) -> str:
    return f"uploads/{uuid.uuid4()}/{file_name}"


def generate_presigned_post(key: str, content_type: str, max_size_bytes: int, expires_in: int = 300):
    return s3_client.generate_presigned_post(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, max_size_bytes],
        ],
        ExpiresIn=expires_in,
    )


def generate_presigned_get(key: str, expires_in: int = 300) -> str:
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': key},
        ExpiresIn=expires_in,
    )


def object_exists(key: str) -> bool:
    from botocore.exceptions import ClientError
    try:
        s3_client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] in ('404', 'NoSuchKey'):
            return False
        raise


def delete_object(key: str):
    s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)


def get_object_head_bytes(key: str, num_bytes: int = 2048) -> bytes:
    obj = s3_client.get_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key,
        Range=f'bytes=0-{num_bytes - 1}',
    )
    return obj['Body'].read()


def get_object_bytes(key: str) -> bytes:
    obj = s3_client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
    return obj['Body'].read()


def put_object(key: str, body, content_type: str):
    s3_client.put_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
