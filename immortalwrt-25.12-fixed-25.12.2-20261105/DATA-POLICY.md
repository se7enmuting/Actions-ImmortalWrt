# 固定版程序与滚动数据的边界

对比官方 25.12.0（标签页 5 月 25 日）、25.12.1（7 月 6 日）、25.12.2（9 月 6 日）时，使用各版本 x86/64 的 `feeds.buildinfo` 定位发布时软件源提交，没有以当前维护分支替代历史配方。

| 官方基线 | packages 提交 | V2Ray GeoIP | V2Ray GeoSite | OpenClash 四库更新地址 |
|---|---|---|---|---|
| 25.12.0 | 881bc2200a61 | 202605120112 | 20260518025449 | 滚动来源 |
| 25.12.1 | e93a938c6312 | 202605120112 | 20260518025449 | 滚动来源 |
| 25.12.2 | 84bd86384928 | 202607171233 | 20260726062913 | 滚动来源 |

官方证据：[25.12.0 feeds](https://downloads.immortalwrt.org/releases/25.12.0/targets/x86/64/feeds.buildinfo)、[25.12.1 feeds](https://downloads.immortalwrt.org/releases/25.12.1/targets/x86/64/feeds.buildinfo)、[25.12.2 feeds](https://downloads.immortalwrt.org/releases/25.12.2/targets/x86/64/feeds.buildinfo)。对应提交的 `net/v2ray-geodata/Makefile` 明确指定数据日期和 HASH；`net/open-app-filter/Makefile` 固定源码提交。三版 OpenClash 默认配置的四个更新地址均指向 release 分支的滚动数据。

本仓库固定版的 packages/luci 已选用较官方 v25.12.2 发布时更新的固定提交；本次不撤销这些既有选择，也不改动其 V2Ray 数据、OAF 特征库、程序版本及已审阅安全回移。

## 本仓库采取的策略

- 有明确版本/格式配套的程序、OAF 特征库、V2Ray GeoIP/GeoSite、CA 与时区数据继续保留当前固定配方，审阅后再更新。
- OpenClash 四库按照 [geodata.policy.json](geodata.policy.json) 的固定来源每次获取当前内容；GeoIP/GeoSite 解析同一次 Release，实际提交、资产和摘要写入本次 build-lock.json。
- 没有显式版本约束不等于官方承诺永久向后兼容。因此两种 geodata 模式均使用固定 Meta 执行 `-t`，覆盖 MMDB、ASN 与 DAT 的规则加载；不开放代理监听。
- 在线下载、上游摘要或固定核心加载任一步失败时，四份文件整体回退到仓库快照；回退集也必须通过 SHA256 及固定核心加载。两者都失败就停止。
- `sources.lock.json` 中 geodata 保留历史基准用于追溯，实际构建用的是本次生成的 build-lock.json 中 geodata；Meta、系统及插件继续固定。
- 两个流程的 Release 说明均列出数据库版本/提交、上游源更新时间（有提供时）、获取时间、online/fallback 和摘要。下载时间不冒充数据库发布时间，托底原因保存在记录中。
- 本策略只覆盖构建时的数据；安装后用户订阅、Rule Provider 和手动更新不属于这次构建输入。

此方案是根据官方配方与滚动更新方式制定的本仓库策略，不宣称官方固定固件本身会在每次构建自动下载这四份最新文件。
