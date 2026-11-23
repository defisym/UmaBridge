# UmaBridge · 赛马娘节点助手

[中文](#中文) · [English](#english) · [Releases](https://github.com/defisym/UmaBridge/releases)

## 中文

UmaBridge 在 Android 手机上把上游 Clash 订阅的入口与 Nasu 出口组合起来，测试整条线路，再把通过的节点加入 Clash 的「赛马娘」分组。助手负责筛选节点，游戏流量由 Clash 转发。

安装包在 [GitHub Releases](https://github.com/defisym/UmaBridge/releases) 中。选择最新正式版的 arm64 APK，下载后按 Android 提示完成安装。

### 快速开始

适用于 Android 9 及以上的 arm64 设备。准备一条 HTTPS Clash YAML 订阅，以及能使用生成配置的 Clash Meta for Android。

1. 打开助手，点「导入」，填入上游订阅地址。
2. 在「设置 → 测速设置」可启用「允许直连」以同时测试单层 Uma OpenVPN，或启用「仅使用上游节点」以同时测试单独的上游入口。两项可独立启用。在「勾选追加跳转入口」中选中要使用的入口，点「应用节点选择」。等首页显示可用节点，就能看到各条线路的平均延迟。
3. 点「复制本机链接」，在同一部手机的 Clash 中导入该 URL 并启用配置。游戏节点在「赛马娘」分组，「默认」「直连」固定在顶部，实际线路按延迟排序。首次有测速结果时默认选中排名第一的实际线路。

本机链接指向手机的回环地址。Clash 更新订阅时需要助手的本机服务正在运行。

### 选择订阅方式

| 链接 | 适用场景 |
| --- | --- |
| 首页的「复制本机链接」 | Clash 请求时触发刷新。默认等待 2500 毫秒，期间测速完成就返回完整结果。超时优先返回本轮已取得的上游，后台继续测速。 |
| 「设置 → 更新推送」中的推送订阅 | 先返回最新上游及游戏节点集合的地址。开启推送后，测速完成会自动更新游戏出口，也可自动选中平均延迟最低的出口。 |
| 「设置 → 复制未筛选链接」 | 手动模式直接返回最新上游与未筛选候选拼成的完整配置，可在 Clash 中自行测速。 |

**设置推送。** 打开「设置 → 更新推送」，复制控制器地址和密钥，分别填入 Clash「设置 → 覆写」的 External Controller 和 Secret，应用覆写并启动 Clash。回到助手开启推送并保存，将推送订阅链接导入 Clash 并选用。首次测速期间，游戏组会先显示「暂无可用出口」。以后上游入口参数、分组或规则改变时，在 Clash 里更新一次完整配置。

### 常用设置

- **本机订阅等待时间。** 在「设置 → 订阅等待时间」输入毫秒数，或开启「无限等待」等到本轮结束。计时从 Clash 请求更新开始。到期时若新上游仍在下载，有匹配的旧配置就先返回旧配置；首次没有缓存时会等到上游就绪。输入 0 表示有配置可用就立即响应。手动链接和推送订阅各自按上表返回。
- **测速与自动刷新。** 「设置 → 测速设置」默认用 4 个线程测 2 轮，轮间等待 200 毫秒。这里可以开启后台自动刷新（最短 15 分钟）、后续轮次全灭时回退，以及让正式订阅只返回上次结果。自动刷新需要本机服务运行。
- **后台优先复测。** 打开「测速设置 → 后台刷新时优先复测现有节点」，Clash 请求、服务启动和定时刷新会先拉取上游并复测所有匹配的已有游戏线路一轮。至少一条通过就直接发布；没有旧线路或全部未通过再完整测速。后台并发上限取设置值与系统可识别的能效核心数中的较小值。
- **更新最优节点。** 展开常驻通知可手动测试 Clash 当前游戏组的全部实际节点一轮，选中延迟最低的可用节点。手动复测全部未通过时保留当前选择。「设置 → 更新推送 → 自动更新最优节点」可独立开启，默认关闭，间隔默认 15 分钟。需要允许使用情况访问并配置本机 Clash 控制器。仅在亮屏解锁、日服赛马娘位于前台时按间隔复测，全部未通过会启动完整测速。「默认」沿用上游兜底规则，「直连」走 DIRECT，两项均不计入测速。
- **候选太少。** 在「Nasu 筛选」调整地区、站点、排序和候选数，或在「可用节点补测」设置下限。多个入口可以搭配同一出口。
- **通知与排错。** 常驻通知标题栏显示可用节点数，通知时间由系统显示。空闲时可点「立即刷新」或「更新最优节点」，测速期间可点「停止刷新」。首页和通知都显示耗时，不满一分钟时只显示秒数。最近一次成功刷新的时间可在首页查看。「设置 → 检测详情」可以查看开机启动情况、最近的进程退出原因，并复制原始测速日志。
- **界面外观。** 在「设置 → 界面外观」选择系统主题（Android 12 及以上支持 Material You）或经典主题。下方的「语言」默认跟随系统，关闭「跟随系统」即可手动选择中文或 English。点「保存」应用两项设置。点击首页分组标题可以展开或收起列表。

「设置 → 设置导入与导出」可通过系统文件选择器保存或恢复 JSON 备份。备份包含上游订阅地址、已应用的入口、筛选与测速、推送、等待时间、开机自启动和外观语言。文件含明文订阅地址和 Clash 控制器密钥，请妥善保管。导入会替换设置，沿用当前设备的本机订阅链接和服务暂停状态。备份包括前台自动选点开关、间隔及后台优先复测设置。旧版备份可直接导入，新设置采用默认值。系统权限需要在目标手机授予。测速缓存和日志不随备份迁移。

### 应用更新

当前版本卡片位于页面顶部，发现新版后，两张卡片并排显示，左侧是当前版本，右侧是待更新版本。下方的日志可以分别展开或收起。有新版时，新版日志在前并默认展开；只有当前版本时，默认展开当前版本日志（如有）。

在「设置 → 检查更新」查看当前显示版本与内部版本。检查公开正式版时先比较显示版本，再比较内部版本号（如 `26112301` 代表 2026 年 11 月 23 日第 01 包）。发现新版后显示待更新版本和该次发布的更新日志。点「下载更新」交给 Android 系统下载管理器，可在完成前取消。校验 APK 后，点「安装更新」并在系统窗口确认。「打开发布页面」可浏览全部版本。此功能按需检查。


分享链接转换器沿用同版本 Mihomo 的解析规则，集成源码和构建说明随 APK 提供。

## English

UmaBridge is an Android companion for Clash Meta for Android. It pairs entries in your upstream Clash subscription with Nasu exits, tests each complete route and adds working routes to the 赛马娘 group. Clash forwards the game traffic.

### Install and connect

1. Download the arm64 APK from [Releases](https://github.com/defisym/UmaBridge/releases) and follow the Android installer prompts. UmaBridge supports Android 9 and later.
2. Tap **Import** and enter your upstream HTTPS Clash YAML subscription URL.
3. Under **Settings → Test settings**, enable **Allow direct connections** to also test standalone Uma OpenVPN routes, or **Use upstream nodes only** to also test each selected upstream on its own. Both switches are off on a fresh install. Select the upstream entries you want to test, then tap **Apply node selection**. The home screen lists working game routes in order of average latency.
4. Tap **Copy local URL**, import that URL into Clash on the same phone and activate the profile. Keep the local UmaBridge service running when Clash refreshes the subscription. The game group places the default and direct options above the tested routes.

### Subscription options

| Mode | What Clash receives |
|---|---|
| Local URL | A refresh starts when Clash requests the subscription. The default wait is 2,500 ms. When the wait expires, the app can return the new upstream and continue testing. A saved configuration can cover a slow upstream. On the first request without a cache, the app waits for the upstream. |
| Push updates | The new upstream and a reference to the game provider are returned first. When testing finishes, the app updates the provider and can select the fastest available route. |
| Unfiltered URL | The latest upstream combined with the candidate routes for manual testing in Clash. |

To configure push, open **Settings → Push updates**, then copy the controller address and secret to the External Controller and Secret fields under Clash overrides. Apply the overrides, enable push in UmaBridge, save, then import and activate the push URL in Clash. Refresh the full Clash profile when the upstream group structure, entry parameters or rules change.

### Tests, notifications and backups

- **Test settings** defaults to four threads and two rounds, 200 ms apart. You can enable background refresh at intervals of at least 15 minutes. The optional current-route retest checks every matching game route once and starts a full test if none pass.
- **Update best node** in the expanded notification tests the current game routes and selects the fastest working one. Automatic testing while the Japanese game is in the foreground needs Android usage access and the local Clash controller. If all current routes fail during that automatic check, UmaBridge starts a full test.
- **Nasu filters** controls countries, sites, ordering and candidate counts. **Test more candidates** can request further batches when the initial pool produces too few usable routes.
- Use the ongoing notification to start or stop a refresh. The app and notification show elapsed time. Diagnostics contains recent errors and test logs.
- **Appearance** offers theme and language controls. The default language follows Android.
- **Import and export settings** transfers configuration and applied entry selections as JSON. The file includes the upstream subscription URL and controller secret in plain text. Store it privately. System permissions, logs and test caches stay on the device. Older backups use the defaults for missing fields.

### App updates

Open **Settings → Check for updates** to see the installed build’s notes, if available. The installed version is at the top. When an update is available, its card appears alongside the installed version, on the right. Below the cards, the available version’s notes come first and are expanded by default. Tap either notes heading to expand or collapse it independently. UmaBridge compares numeric display versions, then compares the build number for revisions of the same version. For example, build `26112301` is the first build on 23 November 2026. When an update is available, the page shows both versions and the release notes. **Download update** starts Android Download Manager. You can cancel the download. After verifying the file and its signing certificate, tap **Install update** and confirm with Android. **Open releases page** lets you choose a version manually.

### Licenses

UmaBridge uses the [MIT license](LICENSE). The bundled Mihomo executable is the unmodified [v1.19.34 upstream release](https://github.com/MetaCubeX/mihomo/releases/tag/v1.19.34). Its [GPL-3.0 license](licenses/mihomo-LICENSE.txt) and [corresponding source information](licenses/probe-source.txt) are included.

The share-link converter uses the same Mihomo parser. Its integration source and build instructions are included in the APK.
