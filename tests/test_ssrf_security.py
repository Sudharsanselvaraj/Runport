"""Unit tests for SSRF protection and safe URL validation."""

import pytest
from runport.core.security import SSRFSecurityError, validate_safe_url


def test_ssrf_blocks_cloud_metadata():
    """Cloud metadata endpoints (169.254.169.254) are strictly blocked."""
    metadata_urls = [
        "http://169.254.169.254/latest/meta-data",
        "http://169.254.169.254/computeMetadata/v1",
        "http://169.254.1.1/internal",
    ]
    for url in metadata_urls:
        with pytest.raises(SSRFSecurityError, match="Link-local / Cloud metadata"):
            validate_safe_url(url)


def test_ssrf_blocks_private_networks_by_default():
    """RFC1918 private IPs are blocked by default."""
    private_urls = [
        "http://10.0.0.1/admin",
        "http://172.16.5.10:8080/metrics",
        "http://192.168.1.1/api",
    ]
    for url in private_urls:
        with pytest.raises(SSRFSecurityError, match="Private network address"):
            validate_safe_url(url)


def test_ssrf_blocks_localhost_by_default_allows_when_configured():
    """Localhost / 127.0.0.1 blocked by default; allowed when allow_localhost=True."""
    with pytest.raises(SSRFSecurityError, match="Loopback address"):
        validate_safe_url("http://127.0.0.1:11434/api/generate")

    with pytest.raises(SSRFSecurityError, match="'localhost' is blocked"):
        validate_safe_url("http://localhost:8000/api")

    # Allowed when allow_localhost=True
    assert validate_safe_url("http://127.0.0.1:11434/api/generate", allow_localhost=True) == "http://127.0.0.1:11434/api/generate"
    assert validate_safe_url("http://localhost:8000/api", allow_localhost=True) == "http://localhost:8000/api"


def test_ssrf_allows_public_domains_and_allowlist():
    """Public domains and allowlisted hosts pass validation."""
    assert validate_safe_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert validate_safe_url("https://openrouter.ai/api/v1") == "https://openrouter.ai/api/v1"

    # Allowlisted host bypasses default private block
    assert validate_safe_url("http://192.168.1.50:5000/workflow", host_allowlist=["192.168.1.50"]) == "http://192.168.1.50:5000/workflow"
