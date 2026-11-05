# Actions-ImmortalWrt

通过 GitHub Actions 手动编译适用于 PVE/KVM 的 x86_64 路由固件。提供**最新版**和**固定版**两套独立流程。

## 选择构建流程

| 流程 | 运行入口 | 更新行为 |
|---|---|---|
| **Latest 25.12（默认使用）** | [Run workflow](https://github.com/se7enmuting/Actions-ImmortalWrt/actions/workflows/build-immortalwrt-latest.yml) | 每次运行获取 25.12 维护分支、独立插件主分支、Meta Alpha 和数据库的最新版本 |
| **Fixed 25.12.2 / 20261105** | [Run workflow](https://github.com/se7enmuting/Actions-ImmortalWrt/actions/workflows/build-immortalwrt-fixed-25.12.2-20261105.yml) | 保留 2026-11-05 的锁定版本，包含服务启动修正，用于构建旧版本基线 |

进入对应 Actions 页面 → **Run workflow** → 选择 main → operation 选择 **build**。默认上传 Artifact，并发布独立 Release，保留以前的 Release。

- `operation=configure`：获取来源、检查依赖及配置，不编译固件、不发布 Release。
- `publish_release=false`：只上传 Artifact，保留 30 天。
- 两套流程都**只允许手动运行**。推送、PR 和定时任务均不会自动编译，也不会自动刷入设备。
- 固定版与最新版的 Artifact、Release 标签和标题分别命名，互不覆盖。

## 最新版如何更新

1. 开始运行时解析上游分支的当前提交，以及最新发布文件。
2. 获取并校验 Meta Alpha、Country.mmdb、GeoIP.dat、GeoSite.dat、ASN.mmdb；保存实际使用的文件和 SHA256。
3. 本次构建只使用已解析的提交和文件，不在编译中途再次追新。
4. 固件随附 `build-lock.json`、软件包清单、配置和 `SHA256SUMS`，可核对每次的实际版本；旧固件保留用于回退。

**不需要人工修改锁文件。** 最新版目录中的 [sources.json](immortalwrt-25.12/sources.json) 只规定跟随哪些来源；`build-lock.json` 是每次运行自动生成的记录，不提交回仓库。上游没有变化时，两次构建的组件版本可以相同。

| 组件 | 最新版跟随范围 |
|---|---|
| ImmortalWrt 系统及原生基础软件源 | `openwrt-25.12` 最新维护代码，包括内核及该分支的软件包更新 |
| OpenClash | 官方 `master` |
| Meta 内核 | OpenClash 官方 `core` 分支下 `master/meta` 的最新 **Alpha linux-amd64-v2**，校验同一提交的官方 SHA256 |
| PassWall / Xray / sing-box 等依赖 | Openwrt-Passwall 官方两个仓库的 `main` 打包配方 |
| Bandix 后端打包 / LuCI | 作者仓库的 `main` |
| Argon / 配置插件、OpenAppFilter | 作者仓库的 `master` |
| Country.mmdb | alecthw 数据库仓库 `release` 下的最新 lite 数据库 |
| GeoIP.dat / GeoSite.dat | Loyalsoldier 最新 Release，二者取同一次发布 |
| ASN.mmdb | xishang0128/geoip 滚动 `latest` 发布 |

这里的“最新”是**上述分支或打包配方提供的最新版本**。例如 Xray 和 Bandix 的二进制版本由上游打包配方决定，不自行替换为可能尚未配套的新二进制。系统保留 25.12 系列，不自动跨大版本，也不混入系统 master；维护分支构建可能显示 `25.12-SNAPSHOT`，这不同于系统 master 开发版。

## 固件功能

| 项目 | 配置 |
|---|---|
| 平台 | x86_64，PVE/KVM，BIOS/UEFI，ext4/squashfs，QCOW2 |
| 代理 | OpenClash＋Meta Alpha amd64-v2、PassWall（Xray＋sing-box） |
| 流量及限速 | Bandix、nlbwmon、vnStat2，支持配置设备上下行限速 |
| 应用识别限制 | OpenAppFilter；最新版采用上游新版 `luci-app-oaf` |
| 动态 DNS | 原生 LuCI 动态 DNS，Cloudflare、DNSPod API v3 |
| 证书续签 | 原生 ACME、acme.sh DNS API、中文管理页面；配置后自动续签 |
| 界面及其他 | Argon、简体中文、WOL、UPnP、QEMU Guest Agent |
| 排除 | KMS、DDNS-Go、PassWall2、SQM、旧 wrtbwmon 和旧管控插件 |

两套流程均默认启动应用过滤后台，开启应用过滤与应用记录，不预设应用屏蔽规则；首次启动通过原生服务初始化特征库，避免仅有驱动而后台未运行导致页面一直等待、设置无法保存。固定版保留软件版本，同步补上服务启动遗漏。

| 服务 | 默认状态与启用方式 |
|---|---|
| 应用过滤 | 后台自启，首次启动立即运行；过滤与记录开关开启，不预设屏蔽应用 |
| OpenClash、PassWall | 功能开关关闭，保留自启入口；页面配置并开启后，重启按保存的配置运行 |
| UPnP | 功能开关关闭，保留自启和配置触发链；以后由原生页面开启 |
| DDNS、ACME | 配置后启用；DDNS 页面 Start DDNS 会开启自启，ACME 按操作说明启用和签发 |
| Bandix、nlbwmon、QEMU Guest Agent | 后台自启 |
| vnStat2 | 原生服务自启，需在页面选择真实 WAN 接口后统计 |
| WOL、Argon | 无独立常驻后台 |

GitHub Actions 工具仍固定经过选择的稳定提交；它们是构建工具，不是固件组件。

## 使用前阅读

- [最新版插件来源、默认开关和输出说明](immortalwrt-25.12/README.md)
- [固定版配方与锁文件](immortalwrt-25.12-fixed-25.12.2-20261105/README.md)
- [最新版固件配置](immortalwrt-25.12/config.seed)
- [ACME 配置及现场迁移经验](immortalwrt-25.12/OPERATIONS.md)
- [固件下载](https://github.com/se7enmuting/Actions-ImmortalWrt/releases)

固件不包含密码、订阅及 DDNS 密钥。先使用隔离的 PVE 测试虚拟机验证；编译成功不代表实际网络功能已验收。最新版可能因上游变更出现不兼容；流程会保留诊断并停止，不会悄悄退回旧组件。

## 上游与许可

系统源码来自 [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)，其余来源见 [sources.json](immortalwrt-25.12/sources.json) 和每次产物中的 `build-lock.json`。

本仓库的构建脚本及文档使用 MIT 许可。固件包含的内核、软件包和上游二进制分别遵循各自的许可证。
