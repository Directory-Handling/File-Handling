"""
Verifies that an incoming SNS message genuinely came from AWS, without
depending on the abandoned `sns-message-validator` package (which pins
a 2019-era `cryptography` version that no longer builds on modern Python).

Implements AWS's documented verification steps directly:
https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html
"""
import base64
import logging
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger('upload.sns_verify')

# AWS-owned domains only — never fetch a signing cert from anywhere else,
# or a spoofed message could point you at an attacker-controlled "cert"
ALLOWED_CERT_HOSTS_SUFFIX = ".amazonaws.com"

_cert_cache = {}


def _get_signing_cert(cert_url: str):
    parsed = urlparse(cert_url)
    if parsed.scheme != "https" or not parsed.netloc.endswith(ALLOWED_CERT_HOSTS_SUFFIX):
        raise ValueError(f"Refusing to fetch signing cert from untrusted host: {parsed.netloc}")

    if cert_url not in _cert_cache:
        resp = requests.get(cert_url, timeout=10)
        resp.raise_for_status()
        _cert_cache[cert_url] = serialization.load_pem_x509_certificate(resp.content)

    return _cert_cache[cert_url]


def _build_string_to_sign(message: dict) -> bytes:
    msg_type = message.get("Type")

    if msg_type == "Notification":
        fields = ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"]
    else:  # SubscriptionConfirmation / UnsubscribeConfirmation
        fields = ["Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"]

    parts = []
    for field in fields:
        if field in message and message[field] is not None:
            parts.append(field)
            parts.append(str(message[field]))

    return ("\n".join(parts) + "\n").encode("utf-8")


def verify_sns_message(message: dict) -> bool:
    """Returns True if the message's signature is valid, False otherwise."""
    try:
        cert = _get_signing_cert(message["SigningCertURL"])
        signature = base64.b64decode(message["Signature"])
        string_to_sign = _build_string_to_sign(message)

        cert.public_key().verify(
            signature,
            string_to_sign,
            padding.PKCS1v15(),
            hashes.SHA1(),  # SNS uses SHA1 for SignatureVersion "1"
        )
        return True
    except Exception:
        # Deliberately broad: a verification failure (bad signature,
        # unreachable cert host, malformed message, network error) must
        # always resolve to "reject this request", never crash the view
        # with a 500. Logged so real infra issues are still visible.
        logger.warning("verify_sns_message: verification failed", exc_info=True)
        return False
