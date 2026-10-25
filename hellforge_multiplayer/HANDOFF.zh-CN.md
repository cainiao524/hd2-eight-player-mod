# HellForge 多人项目交接

更新：2026-10-25（Asia/Taipei）。这是当前主线；`github_handoff_20260927` 保存旧交接与证据。旧完整目标文件继续保留原始字节，最终八名真人同任务的验收要求不降低。

## 这次迁移改变了什么

原来的第一阻碍是官方运行环境中 Party wrapper 的共同 dispatcher 与调用栈契约。HellForge 0.2.0-beta 的源码已经提供 `native/sdk-shims/party_shim.cpp`、`lobby_shim.cpp` 和 `src/HellForge.LocalBackend/Multiplayer/`。当前先从这些源码接口推进，旧 dispatcher 补充采样退为历史路线，不再列为 HellForge 源码工作的前置条件。

这不证明 HellForge 的全部 ABI、游戏内玩家结构和八人同步已满足。SDK shim 的源码接口与真正游戏角色的生命周期是两层。

| 原项目部分 | HellForge 路径或迁移决定 |
|---|---|
| `Native/CapacityContract` | 原样复制进 `mod/src/core/`，来源及 SHA-256 固定在 lock；继续拒绝超出已证明上限的请求 |
| Loader / Lua 启动入口 | 新的 `hellforge_mod_init` 与 SDK 13 清单，不复用旧加载器安装脚本 |
| Party wrapper/dispatcher 分析 | 保留历史；优先研究上游 `party_shim.cpp` 与 `PartyService.cs` |
| Session/接纳 | 对照 `lobby_shim.cpp` 与 `LobbyService.cs`；八节点测试只证明服务层处理，不改游戏发出的容量 |
| `Native/CapacityControl`、`Bridge`、`Sidecar` | 保留旧实现供复用；目前没有绑定到 HellForge 的真实 provider |
| 玩家创建、控制、复制、增援 | 仍需游戏内容器/网络索引适配；不能由 SDK 生成事件代替 |
| 离开/重连 | 结合上游 `netreap.c`；已验证后端清理/重连和合成内存中的原生名册删除/重新插入，未执行 native reaper |
| 实机与发布门槛 | 全部保留：安装整合、单人/两人、第五人、八人完整流程逐项证明 |

## 已查实的容量边界

固定上游 commit：`a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa`。

1. `LobbyService.cs` 创建房间使用请求的 `maxMembers`；加入时检查模组、协议、锁和成员数。内存后端测试能够创建八成员房间，拒绝第九个成员。
2. `PartyService.cs` 使用动态节点/端点集合，按房间成员资格接纳 Party 连接。测试验证了八端点路由与端点块重用。它转发 `maxUsers/maxDevices` 配置，不应把“配置回传一致”解读为已经完整实现各项 SDK 容量约束。
3. `native/mod-loader/event_sources.c` 定义 `EVT_MAX_PLAYERS 4`；`PollPlayers` 超过四人直接返回。`event_polls.c::EvpPlayers` 同样拒绝超过四人。
4. 这些代码的玩家记录为 `manager + 0x2C8 + 0x38*i`，avatar 网络表为 `manager + 0x3A8 + 0x20*i`。根据源码偏移计算，第五条玩家记录起点 `0x2C8 + 4*0x38 = 0x3A8`，与另一张表相交。因此只把 `EVT_MAX_PLAYERS` 改成 8 会把邻接字段当成玩家记录，不能视为正确扩容。
5. 上游明确将房主退出处理为关闭房间；这轮模拟后端验证相同行为，不宣称房主迁移成功。

## 已落地的引擎读取扩展

`engine/0001-shared-player-roster.patch` 已针对固定上游提交重放并编译。新私有接口接入了实际 PollPlayers、EvpPlayers 与 PassivesLocal；经 EvpPlayers 消费的动作人数、本地玩家、治疗、统计和武器读取随之使用统一快照。原版数组仍拒绝超过四项，加载器自己的缓冲区上限为 16。提供者可声明八容量；无效/不可用时不回退到四人视图，解绑等待在途读取，初始化失败释放绑定。

100 项原生合成测试覆盖实际消费者；详细契约、来源、重建命令和局限见 [engine/README.zh-CN.md](engine/README.zh-CN.md)，证据在 `evidence/engine-roster-validation.json`。这一步完成的是加载器读取接口，不是游戏内存储扩容。计分 index<4、customization 四条记录和角色创建/复制的限制仍未解决。

## 已接上的原生存储读取器

`mod/src/ep_native_roster.cpp` 读取旧候选的 B 四数组布局，并核对原管理器计数、哈希表和外部身份票据。它保持 network index 与 ordinal 的区别，持有外部所有者租约期间最多请求 4,096 字节；测试八成员实际请求 2,024 字节。begin/read/end 的生产回调和自动绑定尚未实现。

新增 589 次断言将真实 x64 候选在模拟器中执行八次插入、一次删除压缩、一次重新插入后产生的存储交给读取器，再送入实际 HellForge 消费者。第八名成员移动到第五个位置仍保持原网络索引；重新加入只增加一次生成事件。peer/property/代次等仍是显式合成输入，真实接纳和角色创建没有被证明。详情见 [NATIVE_STORAGE.zh-CN.md](NATIVE_STORAGE.zh-CN.md)。

## 原生属性转发连接

新增八端链路已执行 8 次原生发送/本地索引查询、56 次实际后端转发与原生接收，再对八份存储调用实际 loader；1,678 次消费者断言通过，后端集成模式 264 次检查通过（包含原有 132 次）。不同端使用不同 ordinal 和本地 entity ID，仍保留同一成员的网络索引。详情及固定源码/产物证据见 [NATIVE_SYNC.zh-CN.md](NATIVE_SYNC.zh-CN.md)。

属性描述符拼接和接收实体分派仍是显式测试桥接，完整游戏序列化/分派、confirmed-peer 容量和真实接纳没有被证明。原生发送初值中的 avatar network ID 为 0x7FFF，不能据此宣称创建了角色。后续需要接入角色创建后的更新路径。

## 继续实施顺序

新增 [会话代码所有权模块](SESSION_CODE.zh-CN.md) 已编入研究 Mod，但初始化不调用。它通过 SDK 的真实共用 hook 链发布，先注册回溯表，再固定代码及下一跳变量；尝试发布后，即使 SDK 报错也保留至进程结束。383 次自有进程检查验证五个合成链节点、并发取消拒绝、失败重试边界和独立 DLL 在 FreeLibrary 后保持有效。

[进程内属性生成/重定位](PROPERTY_IMAGES.zh-CN.md) 已接入这个所有者：按实际分配地址生成、封存并登记，失败时清理；清理失败则保留可重试句柄。538 组有效映像与 Python 参考一致、132 组无效输入均拒绝，4 项 API 和 50 项实际配置生命周期检查通过。八端模拟现在执行 C++ 生成的属性代码。

新增 [成组入口与共同切换](PROPERTY_GROUP.zh-CN.md)：发送、接收、getter 三次发布完成前保持旧路由；第一/第二/第三次 SDK 调用失败也不启用候选。355 次自有进程检查验证真实 HellForge 链、并发/重入拒绝、协作排空和模块固定；实际生成的入口另通过 18 组分支测试及 7,169 个 Windows 回溯上下文。生产 guard、完整资源事务、外部拒绝出口及真实数据所有者仍缺失；激活后明确拒绝取消，不能把默认转发或内存保留解释为八人数据已经能回滚。

新增 [实体 ID 到网络索引查询](NATIVE_GETTER.zh-CN.md)：RVA 0x606AD0 的 getter 读取 B 属性区，保留完整 DWORD 与删除压实后的索引对应。C++ 完整映像通过 13 组有效/49 组拒绝比对，7 个既有功能测试和 4,548 个 Windows 回溯上下文通过，实际准备生命周期 25 项通过。保存的单段原回溯资料另核对 32 bytes；八端收到属性后再执行 64 次原生查询。此入口已加入发送/接收共同开关，三者从同一完整 B 地址推导位置；八端查询实际经过新入口。生产自动绑定尚未实现，其余读写入口的统一切换与真正写入排除仍需实现。


新增 [四数组共用搬移器](NATIVE_MOVER.zh-CN.md)：C++ 生成 612-byte 完整映像并接入 READY 准备，100 次功能执行和 8,231 个 Windows 回溯上下文通过；保存的三段原回溯资料另核对 92 bytes。插入/删除/重新加入及八端插入夹具已改用其 C++ 输出。它尚未加入三入口共同开关，生产写入排除和其他写入入口仍待接入。

发送和接收候选各自的 Windows x64 回溯资料与拒绝跳转修正已完成离线验证，八端转发也同时使用两份新候选。见 [NATIVE_UNWIND.zh-CN.md](NATIVE_UNWIND.zh-CN.md)：发送端 12 个场景、1,308 个执行上下文通过 Windows 回溯，对照组复现 3 次旧拒绝跳转错误；接收端将条件保存规范化为入口保存，17 个场景、1,313 个执行上下文通过，对照组复现 7 次错误。接收端另外覆盖 sentinel、空表、满表未命中和碰撞命中。其他候选、运行期有效异常表核对及生产激活/回滚事务仍待完成；两份 unwind 表分别对应各自函数，不可互换。

保存证据中的发送一段、接收四段回溯资料已逐字节核对，共 168 bytes 元数据，均无语言层 handler；10 项来源检查测试通过，两个生成器已强制绑定该来源。保存的 PE 头异常目录尚未完整捕获，所以运行期有效异常表仍未确认。总引擎重建会重新执行来源核对与八端链路；候选映像字节保持不变。上游 hook 会保留整个会话，没有 SDK 撤销入口，生产代码生命期必须与共同链协调。

1. **玩家存储适配**：将既有 Sidecar/Bridge 的权威索引、归属和清理契约逐项映射到 HellForge 所用游戏构建。列出所有固定四项数组及创建/遍历/删除消费者，设计统一外部存储接入，避免只改变数量字段。
2. **引擎扩展边界**：读取接口、可撤销 provider 和 B 布局解码连接已完成离线验证；下一步实现排除并发写入的所有者租约、真实身份票据生产者以及绑定/撤销流程。保持 epoch、generation、稀疏索引和绑定失效语义，不能用模拟八条名册冒充八个已创建角色。
3. **容量事务**：通过有明确生命周期的 native provider，将房间、Party、peer、roster、entity、资源及复制容量作为一个事务提交；失败可回滚，客户端相容性必须检查。现有 SDK 没有可直接完成这一事务的“set_max_players”调用。
4. **生命周期与同步**：加入、角色创建、控制权、复制、死亡/增援、离开/重连、撤离与清理分别测试；与 HellForge 的 hook 链及 netreap 协作。
5. **实机验证**：仅在新的明确授权后进行。先两台电脑各一个客户端，再第五人，最终八个独立账号完整任务。离线八节点从不算真人或游戏客户端。

新增 [四个玩家记录插入入口](NATIVE_INSERT.zh-CN.md)：固定的两种追加、两种密集插入 ABI 已进入 C++ 生成及 READY 准备，保留原 prologue，登记无栈检查与主体两段回溯。9 个测试、515 次功能执行、660 组不同 Windows 回溯状态及 108 项准备生命周期检查通过，原回溯资料重放 88 bytes。生成器直接验证完整 612-byte 搬移器范围；存储和八端夹具同时执行 C++ 插入与搬移。密集入口仍要求 D==T，map/caller 前提未解除；分类、删除及统一写入排除继续作为下一步。

## 验证及重现

入口见 [README](README.zh-CN.md)。`evidence/offline-validation.json` 记录两组实际执行的测试和产物指纹。原始容量核心逐字节相同；固定上游 checkout 无改动；引擎补丁仅在新的源码导出目录重放；新接入层使用真实 SDK 头编译，但测试的 SDK 回调均为模拟值。

不执行上游 `Launch.cmd`、`Build-Engine.ps1`、`Publish-HellForge.ps1` 或 setup：前者会启动应用，后两种流程可能寻找并读取已安装游戏、生成 stand-in 或写入安装目录。这轮只调用本项目显式限定的源码构建入口。

运行授权：`live_capture_authorized=false`、`game_install_authorized=false`、`game_launch_authorized=false`。PID 30776 的旧一次 v2 采样已消费，剩余 0。旧证据、上传收据和 2026-10-19 快照不改写为 HellForge 实测。
