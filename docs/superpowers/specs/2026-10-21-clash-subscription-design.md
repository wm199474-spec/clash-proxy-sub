# 在线代理列表转 Clash 订阅

目标仓库：https://github.com/wm199474-spec/clash-proxy-sub

从 watchttvv/free-proxy-list 的 proxy.txt 读取 HTTP、HTTPS 和 SOCKS5 地址。过滤脱敏或不合法的 IP、非法端口和重复节点，保留地区说明。HTTPS 转为启用 TLS 的 HTTP 节点，默认校验证书。

提供完整 Clash 配置：手动选择、自动测速和统一出口规则。输出 clash.yaml，同时保存源列表 proxy.txt。Python 使用标准库，配置采用 YAML 支持的 JSON 语法，避免额外依赖。

GitHub Actions 每小时第 17 分钟运行，也可手动运行。更新失败或没有完整地址时任务失败，不覆盖现有订阅。只提交生成文件，不强制推送。发布后订阅地址为 https://raw.githubusercontent.com/wm199474-spec/clash-proxy-sub/main/clash.yaml。

先在独立克隆中完成本地实现与验证。遵循用户约定，不执行 Git 提交、推送；临时测试文件在验证结束后删除。节点连通性由 Clash 客户端测速判断，格式转换不保证节点在线。
