"""Production Hardening Service: SSRF Protection, Safe Target Resolution, and Atomic Storage.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import socket
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("prod_hardening")

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),          # Loopback
    ipaddress.ip_network("10.0.0.0/8"),           # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),        # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),       # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local / Cloud Metadata (AWS 169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),            # Current network
    ipaddress.ip_network("::1/128"),              # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),             # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),            # IPv6 link-local
]

ALLOWED_CUSTOM_SCHEMES = {"shopkart", "project", "demo"}


def validate_target_url_safety(url: str, allow_local_demo: bool = False) -> tuple[bool, str]:
    """Validates that a user-supplied target URL does not attempt SSRF against
    internal microservices, cloud metadata endpoints (169.254.169.254), or local networks.
    """
    if not url or not isinstance(url, str):
        return False, "Target URL must be a non-empty string"

    url_str = url.strip()

    # Allow custom internal schemes like shopkart://local or project://proj_123
    for scheme in ALLOWED_CUSTOM_SCHEMES:
        if url_str.startswith(f"{scheme}://"):
            return True, "Safe internal protocol target"

    parsed = urlparse(url_str)
    if not parsed.scheme or parsed.scheme.lower() not in {"http", "https"}:
        return False, f"Target URL scheme '{parsed.scheme}' is unsupported (must be http or https)"

    hostname = parsed.hostname
    if not hostname:
        return False, "Target URL is missing a valid hostname"

    # Hostname string checks
    hostname_lower = hostname.lower()
    if hostname_lower in {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal"}:
        if allow_local_demo:
            return True, "Allowed local demo hostname"
        return False, f"Direct access to '{hostname}' is blocked for security (SSRF protection)"

    # Resolve hostname to IP to prevent DNS rebinding & private IP targeting
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)

            # Check against blocked networks
            for blocked_net in BLOCKED_IP_NETWORKS:
                if ip_obj in blocked_net:
                    if allow_local_demo and (ip_obj.is_loopback or ip_str == "127.0.0.1"):
                        return True, "Allowed local demo address"
                    return False, f"Target resolves to restricted internal IP address '{ip_str}' (SSRF blocked)"
    except socket.gaierror as exc:
        return False, f"Failed to resolve target hostname '{hostname}': {exc}"
    except Exception as exc:
        return False, f"Invalid target network address: {exc}"

    return True, "Target URL passed security safety checks"


def atomic_write_json(file_path: Path, data: Any) -> None:
    """Writes data as JSON atomically using a temporary file and atomic replace.
    Prevents corrupt files if the process crashes or gets terminated mid-write.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = file_path.with_suffix(f".tmp.{os.getpid()}")
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        # Atomic replace on POSIX and Windows (Python 3.3+)
        tmp_file.replace(file_path)
    except Exception:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass
        raise
