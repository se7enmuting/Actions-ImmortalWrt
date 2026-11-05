# 安装后配置与迁移经验

公共固件不包含地点、VM ID、网桥、WAN 账号、订阅、邮箱、域名、证书或 API 密钥。下文的 `example.net` 仅为示例，需要在设备上替换。

## 原生 ACME 自动续签

预装 `acme-common`、`acme-acmesh`、`acme-acmesh-dnsapi`、`luci-app-acme` 和中文翻译。最新版每次使用 25.12 维护 feeds 对应的 acme.sh；具体版本见产物包清单。首次启动保持 ACME 关闭，配置后再启用。

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

2026-11-05 已验证版本的 `ddns-scripts-dnspod-v3` 不要额外填写可选 `record_id`。实测指定该字段会跳过记录查询，后续缺少线路等参数并出现 `InvalidParameter`/无效 JSON。留空可走原生查询、更新流程。配置前确认同名、同类型记录及线路没有歧义，配置后核对 API 实际记录值。没有修改上游脚本强制兼容。

## OpenClash 内核和数据库

固件嵌入 OpenClash 官方 Meta Alpha 通道的 amd64-v2，保持 `core_type=Meta`、`core_version=linux-amd64-v2`。最新版每次从官方 `core` 分支的当前提交解析最新 Alpha、压缩包和官方 SHA256；版本不再固定为 `alpha-gbc76c13`。版本、架构、提交和校验值随产物记录在 `build-lock.json`。固定版流程仍保留原有已验证基线。

PVE 客机需要实际获得完整的 x86-64-v2 指令集，不能只看宿主机型号。可采用 `x86-64-v2-AES` 或经核实的其他 CPU 类型；`host` 并非必须。更改虚拟 CPU 类型通常需要关机再启动。仅更换同版本的 v1/v2 时，OpenClash 更新页面可能因只比较版本号而跳过下载，需另行核对二进制架构。编译版本标题旁的固定星号不是更新或失败状态。

Country.mmdb、GeoIP.dat、GeoSite.dat、ASN.mmdb 每次构建重新获取最新来源并预装，首次启动不必先借助代理下载。GeoIP/GeoSite 使用同一次最新 Release；ASN 跟随滚动 latest 发布。文件摘要随每次运行生成，不沿用旧版 SHA256；上游提供摘要时必须校验一致。实际构建使用已下载、已记录的本次文件，不会中途重新获取滚动地址。安装后的数据库更新与固件构建相互独立。

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

此构建保留与上线环境一致的 `90-cve-2026-98432.nft`，提前丢弃带 IPv4 Options 的入站 TCP 包。它不是内核修复，也不代表 release 内核已含补丁；最新版跟随 25.12 维护分支，不因保留这条临时规则而固定系统源码。确认证实修复的新内核后再审阅并移除该临时规则。

## 本次验收与边界

2026-11-05 的现场迁移验证了 WAN 拨号、IPv4、路由器及客户端 IPv6 HTTPS、代理站点访问、52 个策略组选择保留、DNSPod API v3 实际更新和 ACME 真实签发/部署/续签跳过。

上述现场验收基于当时的固定版本；最新版每次升级后需要重新核对。

这些是现场配置的验证结果，不等于每份新构建或任意网络环境均已验收。固定限速、应用识别拦截、全部端口转发、流量统计口径仍需在各设备及实际流量上分别验证。仓库不分发带个人地址或站点凭据的切换工具。

## 应用过滤后台启动与记录

两套构建均启用原生 `/etc/init.d/appfilter` 开机启动，并在首次初始化提交配置后立即启动。后台 `oafd`、驱动和开关是不同层：只加载 OAF 驱动时，LuCI 用户列表和通过后台保存的设置仍可能无法工作。

固定版使用 `appfilter.global.enable=1`、`record_enable=1`、`auto_load_engine=1`，保持“指定应用”模式；最新版使用 `fwx.appfilter.enable=1`、`fwx.record.enable=1`，驱动由上游原生服务检查加载。最新版的 MAC 过滤仍默认关闭。两套构建均不预置应用屏蔽列表。

首次开启后记录需要实际流量积累。安装后应检查服务开机启动、`oafd` 进程及页面接口，验证开关保存后重启服务仍保留。这些修正进入后续构建的固件，不会自动修改已运行的旧固件；旧固件需在设备上核对并启用原生 appfilter 服务及对应版本的开关。保留配置升级后也应核对启动入口和实际开关。2026-11-05 的现场对话已验证旧版服务恢复后接口正常返回设备记录；这不替代新版固件的实机验收。

## UPnP 页面开关与开机启动

两套构建保留原生 miniupnpd 的开机启动入口，同时保持 `upnpd.config.enabled=0`，首次安装不自动开放 UPnP 映射。原生 LuCI 页面保存的是功能开关；打开该开关后服务按配置运行，重启也可恢复。不要再将 miniupnpd 的开机启动入口另外禁用，否则页面开关与重启后的状态可能不一致。

## 代理开关与开机启动

OpenClash、PassWall 保留原生服务开机启动入口，但 `openclash.config.enable=0`、`passwall.@global[0].enabled=0`，首次安装不自动开启代理，也不在首次初始化中启动代理。以后在原生页面配置并开启，保存的主开关会在重启后继续生效。不能再以禁用 init 自启来实现“代理默认关闭”，否则页面启动可能仅对当前开机有效。

DDNS 原生页面的 Start DDNS 会同时启用自启并启动服务；ACME 的原生启用、首次签发和续签 cron 仍按本文前述步骤执行。它们需要账户或域名配置，不因本次启动修正提前启用。Bandix、nlbwmon、QEMU Guest Agent 保留自启；vnStat 需先选实际统计接口。WOL 与 Argon 不需要单独的常驻后台。

## IPv6 SSH 监听与 WAN 放行

2026-11-05 的现场排查确认过一类迁移遗漏：AAAA 记录指向路由器 LAN 的公网 IPv6，但 Dropbear 被改为只绑定 WAN；同时旧防火墙规则明确拒绝 WAN 入站 IPv6 TCP 22。DNSPod 与 DDNS 均可正常更新，仍无法通过该 IPv6 地址登录。现场分别修正监听和拒绝规则后，IPv4、IPv6 均通过密钥登录验证。

两套配方沿用官方 Dropbear 默认的 LAN 绑定和 WAN 默认拒绝策略，没有写入现场的 WAN 单接口绑定、IPv6 SSH 拒绝规则，也不内置个人公钥或公网管理规则。需要远程 SSH 时，在目标设备完成以下配置：

| 项目 | 要求 |
|---|---|
| 域名地址 | AAAA 应与准备连接的路由器公网 IPv6 一致，区分 WAN 地址与 LAN 的 PD 地址 |
| SSH 监听 | 覆盖 AAAA 指向的本机地址；仅绑定 WAN 不会覆盖 LAN 的 PD 地址。需要双栈通用监听时，可清除对应 Dropbear 实例的 Interface 限制，由防火墙控制访问 |
| 认证 | 先安装并验证自己的公钥；公网管理使用 PasswordAuth=off、RootPasswordAuth=off，不把个人密钥放入公共固件 |
| WAN 规则 | 允许到路由器本机的 TCP 22，family=ipv6、src=wan、target=ACCEPT；来源前缀按实际管理范围设置 |
| 规则冲突 | 检查旧的 Deny-SSH-WAN-IPv6 或等效拒绝规则及顺序，修改或移除冲突项；只在其后追加允许规则可能仍被先行拒绝 |
| 双栈保留 | 保留经确认的 IPv4 SSH 入口，检查 fw4 配置后再重载；通过控制台或现有可信入口操作 |

修改后分别检查监听地址、实际 nftables 入站规则，再从外部执行 IPv4、IPv6 的完整 SSH 密钥登录；TCP 22 连通或 AAAA 正确都不能代替登录验收。LAN 公网 IPv6 属于路由器本机时，配置的是 WAN 入站 input 规则，不是转发到 LAN 主机的端口转发。

固件编译不改变已运行设备的 SSH 与防火墙配置。保留配置升级、旧系统迁移或修改 DDNS 地址来源后，都需要重新核对这两层；应用过滤的自启修正也不会处理 SSH 的监听或入站规则。

## uHTTPd 的 EC 参数与页面校验

原生 uHTTPd 的自签名默认配置可能同时存在 `key_type=ec`、`ec_curve=P-256`、`bits=256`。EC 密钥实际使用曲线参数，`bits` 只用于 RSA 生成路径；但当前 LuCI 页面统一要求该字段至少为 1024，因此 256 会标红，并可能阻止保存其他设置。

两套构建在首次启动或升级后执行 `98-uhttpd-cert-params`：只对 `cert` 类型配置中同时满足 `key_type=ec`、`bits=256` 的条目，将 `bits` 归一为 2048。其他值与 RSA 配置保持原样；不改变 EC 算法、曲线、证书或私钥路径，不删除或重新生成证书，也不重启 uHTTPd。

迁入旧的 uHTTPd 配置后，可运行 `sh /usr/libexec/pve-normalize-uhttpd` 再做配置验收；脚本可重复执行，没有匹配项时不写配置。已运行的旧固件不因仓库更新而自动修正。若在原生页面手工处理，将该字段改为 2048 并保存即可，保留证书路径，不点击“删除旧证书和密钥”。这不会把已有 P-256 证书改成 RSA 2048。
