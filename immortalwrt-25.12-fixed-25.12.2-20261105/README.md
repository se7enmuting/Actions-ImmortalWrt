# ImmortalWrt 25.12.2 · 固定版 20261105

> 本目录保留 2026-11-05 的锁定版本，并补上应用过滤后台的启动遗漏；其余版本不升级。需要每次追新时使用[最新版流程](../README.md)。固定版的 ASN 地址仍为上游滚动链接：若内容变化会因原 SHA256 不匹配而停止，不会自动更新或跳过校验。

适用于 g-pve / b-pve 下的 x86_64 路由虚拟机。两地共用固件，网络、密码、订阅及 DDNS 凭据在安装后分别配置。

## 如何运行

进入仓库 Actions → **Build ImmortalWrt PVE (Fixed 25.12.2 / 20261105)** → **Run workflow**。

- operation=build：编译固件；默认保存 Artifact，并发布独立 Release。
- operation=configure：只准备源码、解析并检查配置，不下载全部编译依赖、不编译固件、不发布 Release。
- publish_release=false：只上传 Artifact；Artifact 保留 30 天，Release 不自动清理。

本 Workflow 只有 workflow_dispatch 触发器。提交代码、PR、定时任务或 repository_dispatch 均不会触发它。只在本仓库保存构建记录和产物，不远程部署。

## 插件范围

| 功能 | 实现 |
|---|---|
| 代理 | 官方源 OpenClash 0.48.002；Meta Alpha alpha-gbc76c13 amd64-v2；官方源 PassWall 26.10.22，Xray＋sing-box |
| 动态 DNS | 原生 luci-app-ddns；Cloudflare、DNSPod 腾讯云 API v3，HTTPS 与 CA 证书 |
| 证书自动续签 | 官方 acme.sh 3.1.3-r3、DNS API 模块、原生中文 LuCI 页面 |
| 设备流量与固定上下行限速 | Bandix 0.12.12（LuCI 0.12.12-r5），在设备规则里配置全天生效的上下行速率 |
| 设备历史统计 | 原生 nlbwmon，按 MAC 汇总；数据库保存到 /etc/nlbwmon，每小时提交 |
| 全网历史统计 | 原生 vnStat2，安装后选择真实 WAN 设备，避免叠加 WAN/WAN6 重复计数 |
| 游戏、视频、聊天应用限制 | ImmortalWrt 官方源 OpenAppFilter，包含匹配本次内核编译的 kmod-oaf |
| 主题 | 官方源 Argon 2.4.7 与配置插件；保留 Bootstrap 备用 |
| 其他 | WOL、UPnP、IPv6、LuCI HTTPS、SFTP、tcpdump、iperf3、dig、QEMU Guest Agent |

不包含 KMS、DDNS-Go、PassWall2、SQM、EQoS、旧 wrtbwmon、ramfree、旧 control-* 插件。不添加设备断网/定时上网插件。Bandix/OAF 本身附带的时间、配额等界面仍按上游保留，但不预设规则。

## 来源与版本

系统内核、基础树锁定官方 v25.12.2 release；packages/luci 使用官方 openwrt-25.12 维护分支在 2026-11-04 核对的固定提交，其他 feeds 使用 release 自带提交。不是 master/SNAPSHOT，也不修改第三方插件源码强制适配。

sources.lock.json 固定全部输入。以后升级要主动审阅并修改锁文件，不会在每次构建时自动追最新。

Bandix 是唯一额外引入的插件源，LuCI 和后端打包仓库均固定提交。后端沿用作者 Makefile 下载并校验的预编译 Rust/eBPF 二进制，不宣称本 Workflow 从 Rust 源码重编该二进制。Meta 使用 OpenClash 官方 core/master/meta 通道的 Alpha amd64-v2，固定到已验证版本的源提交并校验 SHA256，不要求 AVX；PVE 客机需暴露完整的 x86-64-v2 指令集，可采用 x86-64-v2-AES。四份地址/域名/ASN 数据库也按锁文件校验后预装；后续通过 OpenClash 独立更新。

OpenAppFilter 的官方集成目前使用上游 v6.1.8 后端，LuCI 包显示 6.1.4；这是官方配套集成，版本号不等于未维护。没有额外切换到上游 7.x 或修改旧版来强制兼容。

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
- vnStat2 必须在 LuCI 里指定实际出口接口。PPPoE、VLAN、多 LAN、双栈及代理流量的计数口径均需在现场验证。多个统计插件的数字不能直接相加。
- 在独立 PVE VM 上启动，接隔离网络，避免默认 LAN 地址/DHCP 与现网冲突。输出并不自动安装到现有 VM。
- 优先测试设备 IPv4/IPv6 归并、直连与代理计数、上下行限速、指定应用阻断、CPU/内存及历史数据重启保留情况。应用过滤尤其需要分别测试直连、QUIC、代理及双栈场景。
- uHTTPd 的 EC 默认参数 `bits=256` 会有条件归一为 2048，以通过原生页面校验；保留算法、曲线与已有证书，迁入旧配置后的执行方式见 [操作说明](OPERATIONS.md#uhttpd-的-ec-参数与页面校验)。
- SSH 沿用官方 LAN 绑定与 WAN 默认拒绝策略；需要公网 IPv6 SSH 时，分别配置监听和 WAN 入站规则，见 [IPv6 SSH 说明](OPERATIONS.md#ipv6-ssh-监听与-wan-放行)。不能只确认 DDNS 的 AAAA 正确。
- 不整包恢复 18.06 配置。网络接口顺序、WAN/LAN、拨号、DNS 与 IPv6 配置需重新核对。

## 输出与验证范围

输出 BIOS/UEFI 两种启动方式的 ext4、squashfs 镜像，以及 QCOW2 镜像；根分区 2048 MiB、内核分区 64 MiB。新 VM 建议分配至少 4 GiB 虚拟磁盘、2 GiB 内存。

构建先运行 make defconfig，严格核对显式配置，避免插件依赖不满足时被静默取消。构建成功后再核对包清单、BTF/eBPF/VirtIO 内核选项和镜像完整性，才上传固件及发布 Release。

每次输出带 resolved.config、kernel.config、config.buildinfo、包清单、build-lock.json 和 SHA256SUMS。失败构建保留配置及日志供排查。构建通过不等于实际网络功能已验收。

### 上游

- https://github.com/immortalwrt/immortalwrt
- https://github.com/immortalwrt/packages
- https://github.com/immortalwrt/luci
- https://github.com/timsaya/luci-app-bandix
- https://github.com/timsaya/openwrt-bandix
- https://github.com/MetaCubeX/mihomo
- https://github.com/destan19/OpenAppFilter
