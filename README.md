# Clash 公共代理订阅

定时读取 [free-proxy-list](https://github.com/watchttvv/free-proxy-list) 的公开代理列表，生成 Clash Verge / Clash Verge Rev 可用的订阅。

## 订阅地址

首次将本项目发布到仓库的 `main` 分支后，使用：

```text
https://raw.githubusercontent.com/wm199474-spec/clash-proxy-sub/main/clash.yaml
```

在 Clash Verge 的「订阅」页面粘贴地址并导入，启用后进入「代理」选择「自动测速」或手动选择节点。客户端可将订阅更新间隔设置为 60 分钟。

配置包含完整的节点列表、手动选择和自动测速分组。规则模式下，进入 Clash 的流量统一交给「节点选择」分组处理；该分组默认选择「自动测速」。手动选择 `DIRECT` 可切换为直连。

## 自动更新

- GitHub Actions 每小时第 17 分钟读取上游列表；GitHub 的调度可能延迟。
- 也可在仓库的 **Actions → 更新 Clash 订阅 → Run workflow** 手动更新。
- 上游列表的实际更新频率由上游仓库决定，每小时读取并不代表每小时都有新节点。
- 抓取失败、源文件无法解析或没有完整地址时，任务失败并保留上一份订阅。
- 含 `X` 的脱敏 IP、非法 IP/端口和重复记录会被过滤；过滤结果见 Actions 日志。
- `proxy.txt` 是最近一次成功转换时的上游快照。

首次发布后若 Actions 未启用，请在 Actions 页面启用工作流。如果日志提示无法推送，可到 **Settings → Actions → General → Workflow permissions** 确认允许工作流写入仓库；分支保护也可能阻止自动更新。公开仓库长期没有活动时，GitHub 可能停用定时任务，需要手动重新启用。

## 本地运行

只需 Python 3.12 或更新版本，无需安装依赖：

```bash
python scripts/update_subscription.py
```

也可转换本地文件或指定其他来源：

```bash
python scripts/update_subscription.py --input /path/to/proxy.txt
python scripts/update_subscription.py --source https://example.com/proxy.txt
```

可通过 `--output` 和 `--snapshot` 指定配置与源列表快照的保存位置。生成的 `clash.yaml` 使用 YAML 支持的 JSON 语法，可由 Clash 直接解析。

## 节点说明

支持 HTTP、HTTPS 和 SOCKS5；保留地区说明，HTTPS 节点启用 TLS 并使用默认的证书校验。仅包含 IP 的 HTTPS 代理可能因证书不匹配而无法连接。

项目只转换地址格式，不保证免费公共代理在线、速度或可信程度。实际连通性由客户端测速判断；不要通过不可信的公共代理传输明文密码等敏感信息。
