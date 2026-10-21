#!/usr/bin/env python3
"""Convert the public proxy list to a complete Clash subscription (stdlib only)."""

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from health_check import HealthPolicy, filter_healthy


DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/watchttvv/free-proxy-list/main/proxy.txt"
)
ROOT = Path(__file__).resolve().parent.parent


def download_text(url):
    request = Request(url, headers={"User-Agent": "clash-proxy-sub/1.0"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise ValueError("源文件超过 2 MiB，停止更新")
            return data.decode("utf-8-sig")
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def parse_proxies(text):
    proxies = []
    seen = set()
    names = set()
    total = 0
    for raw_line in text.lstrip("\ufeff").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        total += 1
        parts = line.split(maxsplit=1)
        try:
            address = urlsplit(parts[0])
            if address.scheme not in {"http", "https", "socks5"}:
                continue
            host = str(ipaddress.ip_address(address.hostname or ""))
            port = address.port
            if port is None or not 1 <= port <= 65535:
                continue
            if address.path not in {"", "/"} or address.query or address.fragment:
                continue
        except ValueError:
            # Includes masked IPs (such as 95.83.X.62) and malformed ports.
            continue

        username = unquote(address.username) if address.username is not None else None
        password = unquote(address.password) if address.password is not None else None
        key = (address.scheme, host, port, username, password)
        if key in seen:
            continue
        seen.add(key)

        location = parts[1] if len(parts) == 2 else "未知地区"
        location = re.sub(
            r"^入库时间[：:]\s*\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}\s*", "", location
        )
        location = " ".join(location.split()) or "未知地区"
        base_name = f"{location} | {address.scheme.upper()} | {host}:{port}"
        name = base_name
        suffix = 2
        while name in names:
            name = f"{base_name} ({suffix})"
            suffix += 1
        names.add(name)

        proxy = {
            "name": name,
            "type": "socks5" if address.scheme == "socks5" else "http",
            "server": host,
            "port": port,
        }
        if address.scheme == "https":
            proxy["tls"] = True
        if username is not None:
            proxy["username"] = username
        if password is not None:
            proxy["password"] = password
        proxies.append(proxy)

    return proxies, total


def make_config(proxies):
    names = [proxy["name"] for proxy in proxies]
    return {
        "mixed-port": 7897,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": proxies,
        "proxy-groups": [
            {"name": "节点选择", "type": "select", "proxies": ["自动测速", *names, "DIRECT"]},
            {
                "name": "自动测速",
                "type": "url-test",
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "tolerance": 50,
                "proxies": names,
            },
        ],
        "rules": ["MATCH,节点选择"],
    }


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--source", default=DEFAULT_SOURCE, help="源列表 URL")
    source.add_argument("--input", type=Path, help="改为读取本地 TXT 文件")
    parser.add_argument("--output", type=Path, default=ROOT / "clash.yaml")
    parser.add_argument("--snapshot", type=Path, default=ROOT / "proxy.txt")
    parser.add_argument("--report", type=Path, default=ROOT / "health-check.json")
    args = parser.parse_args()

    report_written = False
    destinations_valid = False
    stage = "paths"
    try:
        destinations = {path.resolve() for path in (args.output, args.snapshot, args.report)}
        if len(destinations) != 3:
            raise ValueError("配置文件、源列表快照与检测报告不能使用同一路径")
        destinations_valid = True
        stage = "source"
        text = args.input.read_text(encoding="utf-8-sig") if args.input else download_text(args.source)
        stage = "parse"
        proxies, total = parse_proxies(text)
        if not proxies:
            raise ValueError("没有可转换的完整代理地址，保留上一份订阅")
        candidate_count = len(proxies)
        print(f"开始真实代理检测：{candidate_count} 个候选，每节点两个 HTTPS 目标各测 3 次及小文件下载", flush=True)
        stage = "health_check"
        proxies, report = filter_healthy(proxies, HealthPolicy())
        report["status"] = "passed" if proxies else "failed"
        report["source_records"] = total
        report["invalid_or_duplicate"] = total - candidate_count
        atomic_write(args.report, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        report_written = True
        for node in report["nodes"]:
            print(f"{'通过' if node['passed'] else '过滤'} {node['name']}：{node['reason']}", flush=True)
        if not proxies:
            raise ValueError("没有节点通过质量检测，保留上一份订阅；原因见检测报告")
        stage = "save"
        # JSON documents are also valid YAML; no third-party serializer is needed.
        config = json.dumps(make_config(proxies), ensure_ascii=False, indent=2) + "\n"
        atomic_write(args.snapshot, text)
        atomic_write(args.output, config)
    except (OSError, ValueError, URLError) as error:
        if destinations_valid and not report_written:
            failure = {"checked_at": datetime.now(timezone.utc).isoformat(), "status": "failed",
                       "stage": stage, "error": str(error)}
            try:
                atomic_write(args.report, json.dumps(failure, ensure_ascii=False, indent=2) + "\n")
            except OSError as report_error:
                print(f"检测报告保存失败：{report_error}", file=sys.stderr)
        print(f"更新失败：{error}", file=sys.stderr)
        return 1

    print(f"源列表 {total} 条，完整候选 {candidate_count} 个，质量通过 {len(proxies)} 个，质量过滤 {candidate_count - len(proxies)} 个")
    print(f"配置已写入：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
