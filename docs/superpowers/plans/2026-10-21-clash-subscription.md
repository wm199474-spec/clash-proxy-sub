# Clash Subscription Implementation Plan

> **For agentic workers:** Use executing-plans to implement these steps in this session, without commits or pushes. User instructions take precedence over skill defaults.

**Goal:** 将公开代理 TXT 自动转换为可更新的 Clash 订阅。

**Architecture:** 标准库 Python 脚本下载并解析上游列表，生成完整配置；GitHub Actions 定期运行脚本并保存成功结果。使用新克隆目录隔离已有工作。

**Tech Stack:** Python 3.12+ 标准库、GitHub Actions、Clash YAML（JSON 子集语法）。

## Task 1：先验证转换要求

- [x] 新建临时 `.tmp_conversion_tests.py`，通过脚本 CLI 验证协议映射、地区说明、过滤和去重、认证、空列表保留旧配置、HTTP 下载。
- [x] 运行 `python .tmp_conversion_tests.py`；确认脚本缺失时失败。

## Task 2：实现转换

- [x] 创建 `scripts/update_subscription.py`。接口：`--source URL`、`--input FILE`、`--output FILE`、`--snapshot FILE`；默认读取上游 URL 并写入根目录 clash.yaml 和 proxy.txt。
- [x] 使用 urllib.request 下载，urlsplit 解析，ipaddress 校验 IP，json 生成 YAML 兼容配置。无节点时非零退出，写文件使用临时文件加 os.replace。
- [x] 运行 `python .tmp_conversion_tests.py`；确认所有用例通过。

## Task 3：自动更新与使用说明

- [x] 创建 `.github/workflows/update-subscription.yml`：cron `17 * * * *`、手动触发、脚本变化触发；最小 contents:write 权限、并发串行、无变化跳过提交、中文提交说明、普通 git push。
- [x] 创建 README.md，提供真实订阅 URL、导入步骤、更新和失败行为、免费代理及证书限制。
- [x] 创建 .gitignore，忽略 Python 缓存和临时验证文件。

## Task 4：实际数据与交付

- [x] 从在线源生成 clash.yaml 和 proxy.txt。本机 raw.githubusercontent.com 直连失败，改经 GitHub Contents API 获取原文，用 `python -X utf8 scripts/update_subscription.py --input .tmp_source.txt` 生成；已逐字核对快照与在线源一致。
- [x] 使用本机现有 YAML 解析器验证配置、workflow、分组引用和 TLS，核对源数据数量。
- [x] 删除本任务临时测试文件；运行 `git diff --check` 和 `git status --short`。
- [x] 先交付本地结果，取得用户明确授权提交和推送后再发布订阅。用户已回复“可以”，授权发布到 main。

## 验证记录

2026-10-21：6 项临时 CLI 验证通过，覆盖协议、过滤去重、认证、IPv6、稳定输出、HTTP 下载、失败保留和连接中断后重试。临时验证脚本和源文件已删除。在线列表 30 条，转换 26 条，过滤 4 条；配置和工作流经独立 YAML 解析通过。脚本与工作流已完成独立只读审查，未发现阻断问题。GitHub Actions 的线上运行和节点实际连通性尚未验证。
