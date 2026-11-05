# ImmortalWrt 25.12 Latest · PVE 手动编译

适用于 g-pve / b-pve 下的 x86_64 路由虚拟机。两地共用固件，网络、密码、订阅及 DDNS 凭据在安装后分别配置。

## 如何运行

进入仓库 Actions → **Build ImmortalWrt PVE (Latest 25.12)** → **Run workflow**。

- operation=build：编译固件；默认保存 Artifact，并发布独立 Release。
- operation=configure：只准备源码、解析并检查配置，不下载全部编译依赖、不编译固件、不发布 Release。
- publish_release=false：只上传 Artifact；Artifact 保留 30 天，Release 不自动清理。

本 Workflow 只有 workflow_dispatch 触发器。提交代码、PR、定时任务或 repository_dispatch 均不会触发它。只在本仓库保存构建记录和产物，不远程部署。

## 更新范围

每次运行自动解析 [sources.json](sources.json) 中的上游最新提交与发布文件，生成本次 `build-lock.json`，无需人工升级锁文件。系统与原生 feeds 跟随 `openwrt-25.12`；独立插件跟随各自 master/main。具体来源及边界见[仓库首页](../README.md#最新版如何更新)。

需要旧基线时，使用独立的 **Fixed 25.12.2 / 20261105** 流程。

## 插件范围

| 功能 | 实现 |
|---|---|
| 代理 | 上游 master 的 OpenClash；最新 Meta Alpha amd64-v2；上游 main 的 PassWall 与依赖配方，Xray＋sing-box |
| 动态 DNS | 原生 luci-app-ddns；Cloudflare、DNSPod 腾讯云 API v3，HTTPS 与 CA 证书 |
| 证书自动续签 | 25.12 维护源的原生 acme.sh、DNS API 模块、原生中文 LuCI 页面 |
| 设备流量与固定上下行限速 | 上游 main 的 Bandix 后端打包与 LuCI，在设备规则里配置全天生效的上下行速率 |
| 设备历史统计 | nlbwmon，按 MAC 汇总；数据库保存到 /etc/nlbwmon，每小时提交；Fullcone 连接事件修复见下文 |
| 游戏、视频、聊天应用限制 | 上游 master 的 OpenAppFilter（luci-app-oaf），包含匹配本次内核编译的 kmod-oaf |
| 主题 | 上游 master 的 Argon 与配置插件；保留 Bootstrap 备用 |
| 其他 | WOL、UPnP、IPv6、LuCI HTTPS、SFTP、tcpdump、iperf3、dig、QEMU Guest Agent |

不包含 vnStat/vnStat2、KMS、DDNS-Go、PassWall2、SQM、EQoS、旧 wrtbwmon、ramfree、旧 control-* 插件。不添加设备断网/定时上网插件。Bandix/OAF 本身附带的时间、配额等界面仍按上游保留，但不预设规则。

## 来源与版本

系统内核、基础树及原生 feeds 每次获取 `openwrt-25.12` 的最新维护提交。构建版本可能显示 `25.12-SNAPSHOT`，不代表切换到系统 master。独立插件优先安装上游主分支的配方，并检查实际源码提交及包来源；不修改第三方代码强制适配。

OpenClash 最新 Alpha 的版本文件、压缩包和官方校验表来自 `core` 分支的同一提交；架构固定为 `linux-amd64-v2`，版本号不固定。获取数据库时重新查询上游最新发布；GeoIP/GeoSite 使用同一次 Release。下载只进行一次，编译使用已校验的本次文件，不因上游滚动发布而在中途换版。上游提供摘要时须匹配该摘要，否则记录实际文件的 SHA256。

Bandix 后端沿用作者最新 Makefile 下载并校验的预编译 Rust/eBPF 二进制，本流程不从 Rust 源码重编该二进制。PassWall 的 Xray、sing-box 等使用其依赖仓库最新配方提供的版本，不单独替换二进制。

最新 OAF 与旧集成的 LuCI 包名、配置界面不同，采用 `luci-app-oaf`；不沿用旧 `luci-app-appfilter` 的选择项。最新版主题也可能与固定版界面不同。原生 DDNS、ACME 和 LuCI 基础组件继续使用配套维护源。

固定版本的历史锁文件只保留在独立固定版目录。最新版的 `sources.json` 是跟随策略；每次产出的 `build-lock.json` 才是实际输入记录，不写回仓库。

### nlbwmon 修复与 vnStat 移除

vnStat/vnStat2 页面、翻译与后台已从本配方移除，保留 Bandix 和 nlbwmon。固定版回移官方 `ae5a064` 的 Linux 6.12 连接事件链修复，最新版使用维护分支已有修复；构建后检查实际内核选项，不能只凭服务运行判定采集正常。详见 [修复和验收说明](OPERATIONS.md#nlbwmon-与-fullcone-的连接事件修复)。

## 默认行为与试机

- Argon、简体中文、上海时区；保留官方默认管理地址 192.168.1.1，不嵌入任何现网配置或凭据。
- x86/64 官方内核已内建 VirtIO 网卡、磁盘、SCSI、balloon、console；固件另包含 qemu-ga。PVE 内仍需为新 VM 启用 Guest Agent。
- Bandix 默认接口 br-lan，只开流量模块与历史保存，关闭连接、DNS 和 GeoIP 分析。实际 LAN 接口不同时先修改。监听 127.0.0.1，通过 LuCI 使用。
- 关闭软件/硬件流量卸载，不装 Turbo ACC；Bandix 与应用过滤需要可观察的数据路径。
- 应用过滤后台 appfilter 默认开机启动，首次启动时立即启动并初始化特征库；默认开启应用过滤和应用记录，不预设应用屏蔽规则。只加载 OAF 驱动不足以支持用户列表和保存设置。
- OpenClash、PassWall、UPnP 的功能开关默认关闭，保留原生服务自启入口；在页面开启后，重启仍按保存的配置运行。DDNS、ACME 配置后按原生页面或操作说明启用。两个代理先只启用一个。应用识别不是对任意加密协议或代理隧道的完整保证。
- IPv6 使用新版 odhcpd 原生前缀历史及持久目录，不包含旧版前缀修复脚本和 5 分钟租期改法。
- ACME 首次签发、凭据填写、uHTTPd 自动重载、DNSPod 参数注意事项及离线迁移经验见 [OPERATIONS.md](OPERATIONS.md)。
- 包含与已上线环境一致的临时入站 TCP/IPv4 Options 过滤；这不代表基础内核已修复，详见操作说明。
- 单设备固定限速由 Bandix 的设备上下行规则承担；这是流量限速，不是 SQM 队列公平调度。无需额外安装仅支持 IPv4 的 EQoS。
- 在独立 PVE VM 上启动，接隔离网络，避免默认 LAN 地址/DHCP 与现网冲突。输出并不自动安装到现有 VM。
- 优先测试设备 IPv4/IPv6 归并、直连与代理计数、上下行限速、指定应用阻断、CPU/内存及历史数据重启保留情况。应用过滤尤其需要分别测试直连、QUIC、代理及双栈场景。
- uHTTPd 的 EC 默认参数 `bits=256` 会有条件归一为 2048，以通过原生页面校验；保留算法、曲线与已有证书，迁入旧配置后的执行方式见 [操作说明](OPERATIONS.md#uhttpd-的-ec-参数与页面校验)。
- SSH 沿用官方 LAN 绑定与 WAN 默认拒绝策略；需要公网 IPv6 SSH 时，分别配置监听和 WAN 入站规则，见 [IPv6 SSH 说明](OPERATIONS.md#ipv6-ssh-监听与-wan-放行)。不能只确认 DDNS 的 AAAA 正确。
- 不整包恢复 18.06 配置。网络接口顺序、WAN/LAN、拨号、DNS 与 IPv6 配置需重新核对。

## 输出与验证范围

输出 BIOS/UEFI 两种启动方式的 ext4、squashfs 镜像，以及 QCOW2 镜像；根分区 2048 MiB、内核分区 64 MiB。新 VM 建议分配至少 4 GiB 虚拟磁盘、2 GiB 内存。

构建先检查系统及全部 feeds 的提交、独立插件实际来源，再运行 make defconfig，严格核对显式配置，避免插件依赖不满足时被静默取消。构建成功后再核对包清单、BTF/eBPF/VirtIO 内核选项和镜像完整性，才上传固件及发布 Release。

每次输出带 resolved.config、kernel.config、config.buildinfo、包清单、sources.json、build-lock.json 和 SHA256SUMS。失败构建保留配置及日志供排查。构建通过不等于实际网络功能已验收。

### 上游

- https://github.com/immortalwrt/immortalwrt
- https://github.com/immortalwrt/packages
- https://github.com/immortalwrt/luci
- https://github.com/timsaya/luci-app-bandix
- https://github.com/timsaya/openwrt-bandix
- https://github.com/MetaCubeX/mihomo
- https://github.com/destan19/OpenAppFilter
