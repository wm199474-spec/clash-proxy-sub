# Clash 公共代理订阅

定时读取 [free-proxy-list](https://github.com/watchttvv/free-proxy-list) 的公开代理列表，生成 Clash Verge / Clash Verge Rev 可用的订阅。

## 订阅地址

首次将本项目发布到仓库的 `main` 分支后，使用：

```text
https://raw.githubusercontent.com/wm199474-spec/clash-proxy-sub/main/clash.yaml
```

在 Clash Verge 的「订阅」页面粘贴地址并导入，启用后进入「代理」选择「自动测速」或手动选择节点。客户端可将订阅更新间隔设置为 60 分钟。

配置包含通过质量检测的节点、手动选择和自动测速分组。规则模式下，进入 Clash 的流量统一交给「节点选择」分组处理；该分组默认选择「自动测速」。手动选择 `DIRECT` 可切换为直连。

## 自动更新

- GitHub Actions 每小时第 17 分钟读取上游列表；GitHub 的调度可能延迟。
- 也可在仓库的 **Actions → 更新 Clash 订阅 → Run workflow** 手动更新。
- 上游列表的实际更新频率由上游仓库决定，每小时读取并不代表每小时都有新节点。
- 抓取失败、源文件无法解析、没有完整地址或全部节点未通过质量检测时，任务失败并保留上一份订阅和源快照；保留的旧节点不代表本轮检测通过。
- 含 `X` 的脱敏 IP、非法 IP/端口和重复记录会被过滤；过滤结果见 Actions 日志。
- `proxy.txt` 是最近一次成功转换时的上游快照。
- 成功更新时同时保存 `health-check.json`，记录各节点是否通过及剔除原因；每次工作流也会上传检测报告至 Actions 的 Artifacts，保存 7 天。查看本轮失败信息应以对应工作流日志及附件为准。

## 质量筛选

每次发布前，使用 curl 通过每个代理真实访问 HTTPS 站点，最多并行检测 8 个节点：

1. 对 Google 的 `generate_204` 和 Cloudflare 的 `cdn-cgi/trace` 各请求 3 次，共 6 次，必须全部成功；检查 HTTP 状态码和 Cloudflare 响应内容，不能只凭端口开放判断。
2. 6 次请求的平均总耗时不超过 2.5 秒；单次连接最多 4 秒、请求最多 8 秒。
3. 再从 Cloudflare 下载 256 KiB，必须收到完整文件且平均下载速度至少 64 KiB/s，最长 10 秒。
4. 仅保留全部通过的节点，并按平均请求耗时从低到高排列。

认证失败（407）、证书校验错误、超时、返回登录页、连接不稳定和速度过低都会被过滤。不会为了让 HTTPS 节点通过而自动关闭代理或目标网站的证书校验。

筛选是在 GitHub Actions 的网络环境中完成的，不能保证你本地访问质量相同，也不能保证免费节点长期在线；客户端仍应保留自动测速。256 KiB 下载只用于淘汰明显慢的节点，不代表节点的带宽上限。

首次发布后若 Actions 未启用，请在 Actions 页面启用工作流。如果日志提示无法推送，可到 **Settings → Actions → General → Workflow permissions** 确认允许工作流写入仓库；分支保护也可能阻止自动更新。公开仓库长期没有活动时，GitHub 可能停用定时任务，需要手动重新启用。

## 本地运行

需要 Python 3.12 或更新版本，以及支持 HTTP、HTTPS 代理和 SOCKS5 的 curl 7.70+；Python 无需安装第三方包。GitHub 托管的 Ubuntu 运行器已预装 curl。

```bash
python scripts/update_subscription.py
```

也可转换本地文件或指定其他来源：

```bash
python scripts/update_subscription.py --input /path/to/proxy.txt
python scripts/update_subscription.py --source https://example.com/proxy.txt
```

可通过 `--output`、`--snapshot` 和 `--report` 指定配置、源列表快照和检测报告的保存位置。本地文件转换也必须通过质量检测。生成的 `clash.yaml` 使用 YAML 支持的 JSON 语法，可由 Clash 直接解析。

## 节点说明

支持 HTTP、HTTPS 和 SOCKS5；保留地区说明，HTTPS 节点启用 TLS 并使用默认的证书校验。仅包含 IP 的 HTTPS 代理可能因证书不匹配而无法连接。

项目会筛选当前检测通过的节点，但不保证免费公共代理长期在线、速度或可信程度。实际连通性仍由客户端测速判断；不要通过不可信的公共代理传输明文密码等敏感信息。
