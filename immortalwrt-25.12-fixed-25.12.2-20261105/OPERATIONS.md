# 安装后配置与迁移经验

公共固件不包含地点、VM ID、网桥、WAN 账号、订阅、邮箱、域名、证书或 API 密钥。下文的 `example.net` 仅为示例，需要在设备上替换。

## 原生 ACME 自动续签

预装 `acme-common`、`acme-acmesh`、`acme-acmesh-dnsapi`、`luci-app-acme` 和中文翻译。当前固定 feeds 对应 acme.sh 3.1.3-r3。首次启动保持 ACME 关闭，配置后再启用。

1. 在 LuCI 的 ACME 页面填写真实账户邮箱；官方组件要求 `account_email`。
2. 添加证书，首域名如 `example.net`，另加 `*.example.net`；选择 DNS 验证、`dns_tencent`、`ec256`、Let's Encrypt，关闭测试环境。可设置 `dns_wait=120` 等待传播。
3. 在本机填写凭据变量 `Tencent_SecretId`、`Tencent_SecretKey`，不要填写旧 DNSPod Token。账户需具有查询、创建和删除验证 TXT 记录的权限。
4. 启用后执行 `/etc/init.d/acme enable`、`/etc/init.d/acme start`，再执行 `/etc/init.d/acme renew` 发起首次签发。
5. 成功后，原生证书路径为 `/etc/ssl/acme/example.net.fullchain.crt` 和 `/etc/ssl/acme/example.net.key`。将 uHTTPd 的 `cert`、`key` 分别指向这两个路径，然后首次手动重载 uHTTPd。

官方 uHTTPd 已监听 `acme.renew` 事件，后续成功续签会自动重载；无需改写官方客户端。现有站点如果继续使用自定义证书路径，应在该设备上配置验证、复制和重载的热插拔钩子，不能直接复制其他站点的域名和路径。

官方服务在开始后建立每天本地时间 00:00 的检查任务；未到续签时间自动跳过。这个任务不负责更新 acme.sh 软件本身，客户端和 DNS 模块通过软件包版本管理。账户配置、API 凭据、私钥仅应允许 root 读取；原生状态保存在 `/etc/acme`，证书入口在 `/etc/ssl/acme`。

验收应包含真实签发、验证 TXT 清理、HTTPS 实际证书链及域名核对，以及一次未到期续签跳过。自定义部署钩子、额外证书目录需要加入设备的 `/etc/sysupgrade.conf`；刷机时同样需选择包含 ACME 的新固件。

## DNSPod API v3

DDNS 使用 `dnspod.cn-v3`：用户名为 SecretId，密码为 SecretKey；域名格式为 `主机名@主域名`。启用 HTTPS 和正常 CA 校验，可使用 `/etc/ssl/certs/ca-certificates.crt`。

当前固定版本的 `ddns-scripts-dnspod-v3` 不要额外填写可选 `record_id`。实测指定该字段会跳过记录查询，后续缺少线路等参数并出现 `InvalidParameter`/无效 JSON。留空可走原生查询、更新流程。配置前确认同名、同类型记录及线路没有歧义，配置后核对 API 实际记录值。没有修改上游脚本强制兼容。

## OpenClash 内核和数据库

固件嵌入 OpenClash 官方 Meta Alpha 通道的 amd64-v2，保持 `core_type=Meta`、`core_version=linux-amd64-v2`。当前锁定现网已验证的 `alpha-gbc76c13`，压缩包来自 `core` 分支的固定提交，版本、架构和 SHA256 一同记录；不再默认使用 Mihomo 稳定版。后续追踪新的 Alpha 时更新锁文件并核验兼容性，不能仅修改版本号或跳过校验。

PVE 客机需要实际获得完整的 x86-64-v2 指令集，不能只看宿主机型号。可采用 `x86-64-v2-AES` 或经核实的其他 CPU 类型；`host` 并非必须。更改虚拟 CPU 类型通常需要关机再启动。仅更换同版本的 v1/v2 时，OpenClash 更新页面可能因只比较版本号而跳过下载，需另行核对二进制架构。编译版本标题旁的固定星号不是更新或失败状态。

Country.mmdb、GeoIP.dat、GeoSite.dat、ASN.mmdb 也预装经过 SHA256 校验的基线，首次启动不必先借助代理下载这些数据库。数据库来源和摘要记录在 `sources.lock.json`，它们不是每次构建自动追最新。ASN 发布地址为上游滚动标签，内容变化时校验会失败，需要审阅并更新锁文件，不能跳过校验。

安装后可使用 OpenClash 原生更新功能更新数据库及大陆 IPv4/IPv6 地址列表。先备份、检查配置兼容性，再重启并核对策略组选择、DNS 与客户端连接。内核升级与数据库更新互相独立。

Fake-IP 模式下部分域名的 AAAA 响应可能为空，`curl -6 域名` 的 `000` 不能单独证明 IPv6 链路故障。应分别核对 PD、LAN 地址、IPv6 默认路由、正常 AAAA 域名和直接指定地址的 HTTPS 连接。

## IPv6 与旧系统迁移

使用新版 odhcpd 原生前缀历史，持久目录为 `/etc/odhcpd-piodir`；IPv6 preferred/valid 上限分别为 2700/5400 秒。IPv4 默认租期沿用官方 12 小时。

不迁入旧版 `ipv6-renumber-guard`、hotplug/init 脚本、旧前缀记录、临时旧地址、5 分钟租期和短 RA 间隔。固定绑定可保留 MAC/IP，租期与 IPv6 生命周期分别配置。

不整包导入 18.06 配置：逐项核对接口、WAN、DHCP、明确防火墙规则、端口转发、代理、DDNS 和管理权限。保留新版 WAN 默认拒绝策略；不要迁入旧 WAN 全放行、失效接口、KMS 和废弃脚本，合并完全重复的转发。

订阅设置逐条登记后，用新版 OpenClash 原生更新生成配置，再迁入自定义规则和策略选择并运行核心测试。失效订阅不应冒充单节点；旧 SSL/SSR 参数、旧 DNS 模式等需要核对当前插件支持情况。旧公网 IP 例外、CDN 缓存不能当作永久本地网段继承。

## PVE 切换与回滚

先在隔离 VM 上验证，禁止它提前提供 DHCP/RA 或接生产 WAN。切换前保存快照和明确的原配置；动态 IPv4 租约可单独迁移为 dnsmasq 原生租约数据，避免地址重复分配。

先断开新机网卡，再启用生产配置；新机停机时设置生产 NIC，旧机停止后才能启动新机。共用生产地址和 MAC 的新旧 VM 不得同时运行。确认新机正常后再交换自启动标志，保留原 VM 用于回滚。

自动化处理 `qm config` 的 NIC 字符串时必须替换已有字段。例如 `link_down=0` 应改成 `link_down=1`，不能在末尾再追加同名键。预检与切换前保持旧 OpenClash 的开关状态一致：它启停时会改写 dnsmasq，严格比较配置的预检因此可能停止。

回滚顺序是先关闭新机，再恢复旧机；只恢复新机的隔离快照，不覆盖旧机配置。thin pool 的虚拟容量警告与实际耗尽是不同状态，但应在保存快照前检查实际数据和元数据使用率。

## 临时内核防护

此构建保留与上线环境一致的 `90-cve-2026-98432.nft`，提前丢弃带 IPv4 Options 的入站 TCP 包。它不是内核修复，也不代表 release 内核已含补丁；锁定的系统源码未在本次修改中升级。确认证实修复的新内核后再审阅并移除该临时规则。

## 本次验收与边界

2026-11-05 的现场迁移验证了 WAN 拨号、IPv4、路由器及客户端 IPv6 HTTPS、代理站点访问、52 个策略组选择保留、DNSPod API v3 实际更新和 ACME 真实签发/部署/续签跳过。

这些是现场配置的验证结果，不等于每份新构建或任意网络环境均已验收。固定限速、应用识别拦截、全部端口转发、流量统计口径仍需在各设备及实际流量上分别验证。仓库不分发带个人地址或站点凭据的切换工具。
