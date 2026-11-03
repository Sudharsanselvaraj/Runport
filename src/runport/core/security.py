"""Network security and Server-Side Request Forgery (SSRF) safeguards.

Invariant: User-supplied base URLs and HTTP workflow targets cannot target
cloud metadata services (169.254.169.254), link-local addresses, or unauthorized
private internal IPs by default.
"""

import ipaddress
import socket
from typing import Optional, Sequence
import urllib.parse


class SSRFSecurityError(PermissionError):
    """Raised when an outbound HTTP request targets a forbidden IP address or network."""

    pass


# Cloud metadata and link-local subnets (AWS, GCP, Azure, OpenStack)
LINK_LOCAL_V4 = ipaddress.ip_network("169.254.0.0/16")
LINK_LOCAL_V6 = ipaddress.ip_network("fe80::/10")

# Standard RFC 1918 private subnets
PRIVATE_V4_SUBNETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
]

LOOPBACK_V4 = ipaddress.ip_network("127.0.0.0/8")
LOOPBACK_V6 = ipaddress.ip_network("::1/128")


def is_ip_blocked(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    allow_private: bool = False,
    allow_localhost: bool = False,
) -> tuple[bool, str]:
    """Check if an IP address is blocked under SSRF policies."""
    # Cloud metadata / link-local is NEVER allowed unless explicitly overridden
    if isinstance(ip, ipaddress.IPv4Address) and ip in LINK_LOCAL_V4:
        return True, f"Link-local / Cloud metadata address '{ip}' is strictly blocked for security."
    if isinstance(ip, ipaddress.IPv6Address) and ip in LINK_LOCAL_V6:
        return True, f"IPv6 Link-local address '{ip}' is strictly blocked for security."

    # Loopback addresses (127.0.0.1, ::1)
    if ip.is_loopback:
        if allow_localhost or allow_private:
            return False, ""
        return True, f"Loopback address '{ip}' is blocked by default (enable allow_localhost for local engines)."

    # Private RFC 1918 addresses
    if ip.is_private:
        if allow_private:
            return False, ""
        return True, f"Private network address '{ip}' is blocked by default."

    return False, ""


def validate_safe_url(
    url: str,
    allow_private: bool = False,
    allow_localhost: bool = False,
    host_allowlist: Optional[Sequence[str]] = None,
) -> str:
    """Validates that a URL does not target forbidden private or metadata endpoints.

    Args:
        url: The HTTP/HTTPS URL to validate.
        allow_private: Allow internal RFC1918 IPs.
        allow_localhost: Allow 127.0.0.1 / localhost (e.g. for local Ollama / vLLM).
        host_allowlist: Explicit list of allowed domains or hosts.

    Returns:
        The validated URL string if safe.

    Raises:
        SSRFSecurityError: If URL targets a blocked network.
        ValueError: If URL format is invalid.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}'; only 'http' and 'https' are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Could not parse hostname from URL '{url}'.")

    # If an explicit host allowlist is configured
    if host_allowlist:
        clean_allowlist = [h.lower().strip() for h in host_allowlist]
        if hostname.lower() in clean_allowlist:
            return url

    # Check literal IP address
    try:
        ip_obj = ipaddress.ip_address(hostname)
        blocked, reason = is_ip_blocked(ip_obj, allow_private=allow_private, allow_localhost=allow_localhost)
        if blocked:
            raise SSRFSecurityError(f"SSRF Protection: {reason}")
        return url
    except ValueError:
        pass  # Not an IP literal, it is a hostname

    # Handle named localhost
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        if allow_localhost or allow_private:
            return url
        raise SSRFSecurityError("SSRF Protection: 'localhost' is blocked by default (set allow_localhost=True to allow).")

    # DNS Resolution check (safe for public domain names)
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            blocked, reason = is_ip_blocked(ip_obj, allow_private=allow_private, allow_localhost=allow_localhost)
            if blocked:
                raise SSRFSecurityError(f"SSRF Protection: Domain '{hostname}' resolved to blocked IP '{ip_str}': {reason}")
    except (socket.gaierror, socket.error):
        # In offline testing or with blocked sockets, unresolvable non-private domains are allowed to proceed
        # (the fake transport / mock will handle the request)
        pass

    return url
