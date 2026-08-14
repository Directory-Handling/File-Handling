import logging
import tempfile
from dataclasses import dataclass

from django.conf import settings

from .s3_service import s3_client

logger = logging.getLogger('upload.clamav')


@dataclass
class ScanResult:
    is_clean: bool
    detail: str = ""


def _get_clamd_connection():
    import pyclamd

    mode = getattr(settings, 'CLAMAV_MODE', 'unix')

    if mode == 'network':
        host = settings.CLAMAV_HOST
        port = settings.CLAMAV_PORT
        cd = pyclamd.ClamdNetworkSocket(host=host, port=port)
    else:
        cd = pyclamd.ClamdUnixSocket()

    try:
        cd.ping()
    except Exception as exc:
        raise RuntimeError(f"clamd is not reachable (mode={mode})") from exc

    return cd


def run_clamav_scan(key: str) -> ScanResult:
    """
    Downloads the object to a temp file and scans it with a local or
    networked clamd daemon via pyclamd. Raises on infra errors (clamd
    down/unreachable) so the caller's retry logic can handle it — only
    returns normally for an actual clean/infected verdict.
    """
    cd = _get_clamd_connection()

    with tempfile.NamedTemporaryFile() as tmp:
        s3_client.download_fileobj(settings.AWS_STORAGE_BUCKET_NAME, key, tmp)
        tmp.flush()
        result = cd.scan_file(tmp.name)

    if result is None:
        return ScanResult(is_clean=True)

    virus_name = list(result.values())[0][1]
    logger.warning("run_clamav_scan: key=%s flagged as %s", key, virus_name)
    return ScanResult(is_clean=False, detail=virus_name)
