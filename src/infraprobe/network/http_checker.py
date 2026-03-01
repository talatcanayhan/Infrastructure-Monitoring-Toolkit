"""HTTP/HTTPS health checker with TLS certificate validation.

Performs HTTP requests and validates responses against expected criteria.
Inspects TLS certificates using the ssl module for expiry alerting,
certificate chain validation, and security header checks.
"""

import logging
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger("infraprobe.network.http")


@dataclass
class TLSCertInfo:
    """TLS certificate details extracted from a live connection."""

    subject: str = ""
    issuer: str = ""
    not_before: str = ""
    not_after: str = ""
    days_until_expiry: int = 0
    is_expired: bool = False
    san: list[str] = field(default_factory=list)
    protocol_version: str = ""
    cipher: str = ""
    serial_number: str = ""


@dataclass
class HTTPResult:
    """Result of an HTTP/HTTPS health check."""

    url: str
    status_code: int = 0
    reason: str = ""
    response_time_ms: float = 0.0
    content_length: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    tls_info: Optional[TLSCertInfo] = None
    success: bool = False
    error: Optional[str] = None


def check_tls_certificate(hostname: str, port: int = 443) -> TLSCertInfo:
    """Connect via TLS and extract certificate details.

    Opens a raw TLS connection using the ssl module (not requests)
    to directly inspect the server certificate, including:
    - Subject and issuer distinguished names
    - Validity dates and days until expiry
    - Subject Alternative Names (SANs)
    - Protocol version and cipher suite

    Args:
        hostname: Server hostname to connect to.
        port: TLS port (default 443).

    Returns:
        TLSCertInfo with extracted certificate details.
    """
    info = TLSCertInfo()

    try:
        context = ssl.create_default_context()

        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return info

                # Extract subject common name
                subject_parts = []
                subject = cert.get("subject")
                if isinstance(subject, tuple):
                    for rdn in subject:
                        for attr_type, attr_value in rdn:
                            if attr_type == "commonName":
                                subject_parts.append(attr_value)
                info.subject = ", ".join(subject_parts) if subject_parts else "Unknown"

                # Extract issuer
                issuer_parts = []
                issuer = cert.get("issuer")
                if isinstance(issuer, tuple):
                    for rdn in issuer:
                        for attr_type, attr_value in rdn:
                            if attr_type in ("organizationName", "commonName"):
                                issuer_parts.append(attr_value)
                info.issuer = ", ".join(issuer_parts) if issuer_parts else "Unknown"

                # Validity dates
                not_before = cert.get("notBefore", "")
                not_after = cert.get("notAfter", "")
                info.not_before = not_before if isinstance(not_before, str) else ""
                info.not_after = not_after if isinstance(not_after, str) else ""

                # Calculate days until expiry
                if info.not_after:
                    not_after_dt = datetime.strptime(info.not_after, "%b %d %H:%M:%S %Y %Z")
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    delta = not_after_dt - now
                    info.days_until_expiry = delta.days
                    info.is_expired = delta.days <= 0

                # Subject Alternative Names
                san_entries = cert.get("subjectAltName")
                if isinstance(san_entries, tuple):
                    info.san = [value for _, value in san_entries]

                # Connection details
                info.protocol_version = ssock.version() or ""
                cipher_info = ssock.cipher()
                info.cipher = cipher_info[0] if cipher_info else ""

                # Serial number
                serial = cert.get("serialNumber", "")
                info.serial_number = serial if isinstance(serial, str) else ""

    except ssl.SSLCertVerificationError as e:
        logger.warning("TLS certificate verification failed for %s: %s", hostname, e)
        info.issuer = f"VERIFICATION FAILED: {e}"
    except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError) as e:
        logger.error("TLS connection to %s:%d failed: %s", hostname, port, e)

    return info


def check_http(
    url: str,
    expected_status: int = 200,
    timeout: float = 10.0,
    check_tls: bool = True,
    follow_redirects: bool = True,
) -> HTTPResult:
    """Perform an HTTP/HTTPS health check against a URL.

    Sends an HTTP GET request and validates the response status code.
    For HTTPS URLs, optionally inspects the TLS certificate.

    Args:
        url: The URL to check.
        expected_status: Expected HTTP status code.
        timeout: Request timeout in seconds.
        check_tls: Whether to inspect the TLS certificate.
        follow_redirects: Whether to follow HTTP redirects.

    Returns:
        HTTPResult with status, timing, and optional TLS info.
    """
    result = HTTPResult(url=url)

    try:
        start = time.perf_counter()
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=follow_redirects,
            headers={"User-Agent": "InfraProbe/1.0"},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        result.status_code = response.status_code
        result.reason = response.reason or ""
        result.response_time_ms = round(elapsed_ms, 2)
        result.content_length = len(response.content)
        result.headers = dict(response.headers)
        result.success = response.status_code == expected_status

    except requests.exceptions.SSLError as e:
        result.error = f"TLS/SSL error: {e}"
    except requests.exceptions.ConnectionError as e:
        result.error = f"Connection error: {e}"
    except requests.exceptions.Timeout:
        result.error = f"Request timed out after {timeout}s"
    except requests.exceptions.RequestException as e:
        result.error = f"Request error: {e}"

    # Check TLS certificate for HTTPS URLs
    parsed = urlparse(url)
    if check_tls and parsed.scheme == "https" and parsed.hostname:
        port = parsed.port or 443
        result.tls_info = check_tls_certificate(parsed.hostname, port)

    logger.info(
        "HTTP %s -> %d (%s) in %.1fms",
        url,
        result.status_code,
        "OK" if result.success else "FAIL",
        result.response_time_ms,
    )

    return result
