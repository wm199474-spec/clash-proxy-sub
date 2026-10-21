"""Filter proxies by repeated, certificate-verified HTTPS and download checks."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import ipaddress
import json
import math
import os
import shutil
import subprocess
from urllib.parse import quote


TARGETS = (
    ("google", "https://www.gstatic.com/generate_204"),
    ("cloudflare", "https://www.cloudflare.com/cdn-cgi/trace"),
)
DOWNLOAD_BYTES = 256 * 1024
DOWNLOAD_URL = f"https://speed.cloudflare.com/__down?bytes={DOWNLOAD_BYTES}"
MARKER = b"\n__HEALTH__"


@dataclass(frozen=True)
class HealthPolicy:
    rounds: int = 3
    workers: int = 8
    connect_timeout: int = 4
    request_timeout: int = 8
    download_timeout: int = 10
    max_average_seconds: float = 2.5
    min_download_kib_per_second: float = 64


def proxy_url(proxy):
    scheme = "socks5h" if proxy["type"] == "socks5" else "https" if proxy.get("tls") else "http"
    host = proxy["server"]
    if ":" in host:
        host = f"[{host}]"
    auth = ""
    if "username" in proxy:
        auth = quote(proxy["username"], safe="") + ":" + quote(proxy.get("password", ""), safe="") + "@"
    return f"{scheme}://{auth}{host}:{proxy['port']}"


def probe(proxy, label, url, policy, *, download=False):
    timeout = policy.download_timeout if download else policy.request_timeout
    command = [
        "curl", "--disable", "--silent", "--show-error",
        "--proxy", proxy_url(proxy), "--noproxy", "",
        "--connect-timeout", str(policy.connect_timeout), "--max-time", str(timeout),
        "--max-filesize", str(DOWNLOAD_BYTES if download else 32768),
        "--write-out", "\n__HEALTH__%{json}",
    ]
    if download:
        command += ["--output", os.devnull]
    command += [url]
    result = {"target": label, "ok": False}
    try:
        process = subprocess.run(command, capture_output=True, timeout=timeout + 3)
        body, separator, raw_metrics = process.stdout.rpartition(MARKER)
        # Windows curl can include system-codepage text in its JSON errormsg.
        metrics = json.loads(raw_metrics.decode("utf-8", errors="replace")) if separator else {}
        http = int(metrics.get("http_code", 0))
        connect_http = int(metrics.get("http_connect", 0))
        elapsed = float(metrics.get("time_total", 0))
        speed = float(metrics.get("speed_download", 0)) / 1024
        size = int(metrics.get("size_download", 0))
        if not all(math.isfinite(value) and value >= 0 for value in (elapsed, speed)):
            raise ValueError("Invalid curl timing")
        result.update(http=http, proxy_http=connect_http, seconds=round(elapsed, 4),
                      bytes=size, kib_per_second=round(speed, 2), curl_exit=process.returncode)
        if connect_http == 407:
            reason = "proxy_authentication"
        elif process.returncode in {60, 51}:
            reason = "certificate_validation"
        elif process.returncode == 28:
            reason = "timeout"
        elif process.returncode:
            reason = "proxy_or_tls_connection"
        elif download:
            reason = "" if http == 200 and size == DOWNLOAD_BYTES else "invalid_download"
            if not reason and speed < policy.min_download_kib_per_second:
                reason = "slow_download"
        elif label == "google":
            reason = "" if http == 204 and not body else "unexpected_response"
        else:
            trace = dict(line.partition("=")[::2] for line in body.decode("utf-8", errors="replace").splitlines() if "=" in line)
            try:
                ipaddress.ip_address(trace.get("ip", ""))
                valid_trace = trace.get("h") == "www.cloudflare.com"
            except ValueError:
                valid_trace = False
            reason = "" if http == 200 and valid_trace else "unexpected_response"
        result.update(ok=not reason, reason=reason or "passed")
    except subprocess.TimeoutExpired:
        result["reason"] = "timeout"
    except (OSError, ValueError, TypeError):
        result["reason"] = "probe_error"
    return result


def check_node(proxy, policy):
    samples = []
    node = {"name": proxy["name"], "server": proxy["server"], "port": proxy["port"],
            "passed": False, "successes": 0, "attempts": 0, "samples": samples}
    for _ in range(policy.rounds):
        for label, url in TARGETS:
            sample = probe(proxy, label, url, policy)
            samples.append(sample)
            node["attempts"] += 1
            if not sample["ok"]:
                node["reason"] = sample["reason"]
                return node
            node["successes"] += 1
    average = sum(sample["seconds"] for sample in samples) / len(samples)
    node["average_seconds"] = round(average, 4)
    if average > policy.max_average_seconds:
        node["reason"] = "high_latency"
        return node
    node["download"] = probe(proxy, "download", DOWNLOAD_URL, policy, download=True)
    node["passed"] = node["download"]["ok"]
    node["reason"] = "passed" if node["passed"] else node["download"]["reason"]
    return node


def filter_healthy(proxies, policy):
    if not shutil.which("curl"):
        raise ValueError("未找到 curl，无法执行真实代理检测；保留上一份订阅")
    with ThreadPoolExecutor(max_workers=policy.workers) as executor:
        nodes = list(executor.map(lambda proxy: check_node(proxy, policy), proxies))
    passed = [(proxy, node) for proxy, node in zip(proxies, nodes) if node["passed"]]
    passed.sort(key=lambda item: item[1]["average_seconds"])
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "policy": asdict(policy), "targets": dict(TARGETS),
        "download_url": DOWNLOAD_URL, "candidate_count": len(proxies),
        "passed": len(passed), "rejected": len(proxies) - len(passed), "nodes": nodes,
    }
    return [proxy for proxy, _ in passed], report
