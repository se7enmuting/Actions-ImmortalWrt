# Actions-ImmortalWrt

基于 ImmortalWrt 官方稳定版，通过 GitHub Actions 手动编译适用于 PVE/KVM 的 x86_64 路由固件。

这是独立仓库，使用全新 Git 历史，仅保存本项目的构建流程、配置与说明。

## 开始编译

1. 进入 [Actions → Build ImmortalWrt PVE (Manual)](https://github.com/se7enmuting/Actions-ImmortalWrt/actions/workflows/build-immortalwrt.yml)。
2. 点击 **Run workflow**，选择 main 分支。
3. operation 选择 **build**；默认将成功构建的固件保存到 Releases。
4. 需要只检查依赖和配置时，选择 **configure**，不会生成固件。

**只允许手动运行。** 推送代码、提交 PR 或时间计划均不会自动编译固件。

## 当前方案

| 项目 | 配置 |
|---|---|
| 系统 | 官方 ImmortalWrt 25.12.2；源码和 feeds 固定提交 |
| 平台 | x86_64，PVE/KVM，BIOS/UEFI，ext4/squashfs，QCOW2 |
| 代理 | OpenClash＋Meta Alpha amd64-v2、PassWall（Xray＋sing-box） |
| 流量及限速 | Bandix、nlbwmon、vnStat2，支持配置设备上下行限速 |
| 应用识别限制 | OpenAppFilter |
| 动态 DNS | 原生 LuCI 动态 DNS，Cloudflare、DNSPod API v3 |
| 证书续签 | 原生 ACME、acme.sh DNS API、中文管理页面；配置后自动续签 |
| 界面及其他 | Argon、简体中文、WOL、UPnP、QEMU Guest Agent |
| 排除 | KMS、DDNS-Go、PassWall2、SQM、旧 wrtbwmon 和旧管控插件 |

相关 GitHub Actions 使用原生 Node.js 24 的稳定版本，并固定提交 SHA。

## 使用前阅读

- [插件版本、默认开关、PVE 试机及迁移说明](immortalwrt-25.12/README.md)
- [源码和依赖锁文件](immortalwrt-25.12/sources.lock.json)
- [固件配置](immortalwrt-25.12/config.seed)
- [ACME 配置及现场迁移经验](immortalwrt-25.12/OPERATIONS.md)
- [固件下载](https://github.com/se7enmuting/Actions-ImmortalWrt/releases)

固件不包含密码、订阅及 DDNS 密钥。建议先使用隔离的 PVE 测试虚拟机验证；编译成功不代表实际网络功能已验收。

## 上游与许可

系统源码来自 [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)，插件来源及固定版本见锁文件与详细说明。

本仓库的构建脚本及文档使用 MIT 许可。固件包含的内核、软件包和上游二进制分别遵循各自的许可证。
