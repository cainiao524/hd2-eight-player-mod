# HD2 八人项目：HellForge 适配主线

2026-10-26，Asia/Taipei。当前开发目标转向 **HellForge 0.2.0-beta / SDK 13 / 游戏 build 25480438**。完整目标仍是八名真人、八个独立账号同任务；第五人是中间验收点。

当前完成的是可编译的 SDK 接入层、真实后端源码的离线验证，以及原生玩家读取扩展和八槽存储连接，**尚未实现可玩的五人或八人 Mod**。源码包名称中的 Research 有意保留；启用它不会增加玩家槽位。

## 当前交付

| 内容 | 位置 | 当前作用 |
|---|---|---|
| 已有玩家状态更新 | `mod/src/ep_arrival_image.*` / `NATIVE_STATE_UPDATE.zh-CN.md` | 八槽数组访问与原 GS 异常处理器迁移；第 17 个共同入口；该函数不创建新角色 |
| HellForge 源码 Mod | `mod/` | SDK 入口、版本检查、会话身份和任务/生成/死亡事件观察 |
| 原容量契约 | `mod/src/core/` | 从旧项目逐字节复用；未满足容量验证时拒绝八人请求 |
| 原生接入测试 | `tests/adapter_test.cpp` | 模拟 SDK；同时加载本次构建 DLL 验证实际导出和回调 |
| 八节点后端测试 | `tests/backend/` | 调用上游原版 LobbyService / PartyService，以内存传输验证八节点 |
| 固定版本与来源 | `upstream.lock.json` | 上游 commit、源码校验、编译器指纹、旧核心对应关系 |
| 离线构建入口 | `tools/build_offline.py` | 编译、运行两组测试、生成源码 ZIP 与验证收据 |
| 证据 | `evidence/offline-validation.json` | 实际检查数量、源码和产物指纹、实机门槛 |
| 引擎玩家读取补丁 | `engine/` | 固定 commit、可重放；实际加载器消费者支持外部名册 |
| 原生消费者测试 | `tests/engine_roster_test.c` | 合成进程直接执行补丁后的枚举、生命周期、治疗及本地选择 |
| 引擎构建与证据 | `tools/build_engine_offline.py` / `evidence/engine-roster-validation.json` | 单独编译研究 loader；100 次消费者检查 + 589 次存储连接断言，生产 provider 未绑定 |
| 原生存储连接 | `mod/src/ep_native_roster.*` / `NATIVE_STORAGE.zh-CN.md` | 解码旧原生候选写出的八槽存储；离线验证插入、删除压缩和重新插入 |
| 原生属性转发验证 | `NATIVE_SYNC.zh-CN.md` / `tools/native_roster_sync.py` | 八端原生属性发送、56 次后端转发与原生接收，再进入实际读取器；游戏封包与实体分派仍由测试桥接 |
| 会话代码所有权 | `mod/src/ep_session_code.*` / `SESSION_CODE.zh-CN.md` | 封存映像、注册回溯表、稳定下一跳变量和 SDK hook 链发布；387 次自有进程检查通过，未接入 Mod 初始化 |
| 进程内属性生成 | `mod/src/ep_property_image.*`、`ep_property_code.*` / `PROPERTY_IMAGES.zh-CN.md` | C++ 生成和重定位发送/接收映像，按实际分配地址封存；538 组有效与 132 组拒绝输入匹配，50 项所有权检查通过 |
| 属性成组入口 | `mod/src/ep_property_gate.*`、`ep_property_group.*` / `PROPERTY_GROUP.zh-CN.md` | 发送/接收/getter 三次发布成功后受 guard 约束共同启用；355 次链与生命周期检查，18 组入口分支和 7,169 个回溯上下文通过；生产 guard 仍缺失 |
| 实体到网络索引查询 | `mod/src/ep_getter_image.*` / `NATIVE_GETTER.zh-CN.md` | 使用八槽 B 存储，完整 DWORD 查询；4,550 个回溯上下文、25 项准备生命周期及八端 64 次查询通过；已加入三入口共同开关，未在游戏发布 |
| 两个原生移除入口 | `mod/src/ep_remove_image.*` / `NATIVE_REMOVE.zh-CN.md` | C++ 生成及 READY 准备；2,293 次功能执行、4,670 组不同回溯状态、54 项准备检查通过；存储夹具执行移除后再加入，生产生命周期待接入 |
| 两个原生分类入口 | `mod/src/ep_classify_image.*` / `NATIVE_CLASSIFY.zh-CN.md` | C++ 生成及 READY 准备；853 次功能执行、20,905 组不同回溯状态、54 项准备检查和 359 次分类存储读取断言通过；临时辅助函数是契约替身 |
| 十七入口共同切换 | `mod/src/ep_roster_gate.*`、`ep_roster_group.*` / `ROSTER_GROUP.zh-CN.md` | 同一 S/B 和控制字、十七次发布后才允许提交；插入/移除绑定同组搬移主体；真实 guard 及数据事务未接入 |
| 名册存储所有者 | `mod/src/ep_roster_owner.*` / `ROSTER_OWNER.zh-CN.md` | 受管读写互斥、revision/身份票据原子提交、关闭排空与异常隔离；641 次实际 DLL/loader 检查，生产写入覆盖和真实身份尚未绑定 |
| 离队前资源清理 | `mod/src/ep_departure_image.*` / `NATIVE_DEPARTURE.zh-CN.md` | 独立映像及准备验证通过；4,250 个 Windows 上下文；已接入第 15 个共同入口及同组 getter，真实完整离队事务仍待完成 |
| 原生注册表与关联查询 | `mod/src/ep_registry_image.*` / `NATIVE_REGISTRY.zh-CN.md` | 两个入口、链式回溯、同组内部绑定；8 个测试、87 次执行、3,963 个 Windows 回溯上下文通过，尚未发布到游戏 |
| 十七入口受管调用 | `mod/src/ep_roster_call.*` / `ROSTER_CALLS.zh-CN.md` | 旧/新路径整次调用进入 owner，保存六参数与返回状态；同 owner 嵌套、受管提交及异常隔离，显式选择且未接入初始化 |
| 实体删除外层范围 | `mod/src/ep_roster_gate.*`、`ep_roster_call.*` / `ENTITY_REMOVE_SCOPE.zh-CN.md` | 第 16 个入口保留原 dispatcher，双阶段间隙继续持有 owner；原回调契约和完整游戏执行仍未验证 |
| 原实体删除集成执行 | `tools/validate_entity_remove.py` / `ENTITY_REMOVE_SCOPE.zh-CN.md` | 19 个离线场景实际执行原 dispatcher 的选定路径与 C++ 名册映像；242/373 条原指令覆盖；2 个超额返回反例，真实提供者契约仍未证明 |
| 继续开发说明 | `HANDOFF.zh-CN.md` | 旧代码迁移关系、已知限制、下一步及授权范围 |
| 四个原生插入入口 | `mod/src/ep_insert_image.*` / `NATIVE_INSERT.zh-CN.md` | C++ 生成及 READY 准备；515 次功能执行、660 组不同回溯状态和 108 项准备检查通过；已接入存储/同步夹具，生产共同切换待实现 |

适配器使用 `hellforge_mod_init`、`HfApi::session`、`subscribe`、`on_game_thread` 和 `game_state`。接入失败后已注册的回调保持停用，避免半初始化状态继续运行。初始化与游戏线程之间通过原子标志发布状态。

SDK 事件只算观察次数。死亡后增援会再次生成，且这些事件不提供完整加入/退出名册，因此不把生成次数当成房间人数，不把会话身份当成已绑定容量 provider。`requested_players=8`、`applied_players=0`、`provider_bound=false`、`runtime_verified=false`。

后端测试覆盖：八成员房间、八个独立端点、八端点互相发送、第九成员拒绝、模组不匹配拒绝、非房间成员拒绝 Party 连接、定向消息、满房重连、掉线清理、再次加入、房主退出后各端关闭。所有身份都是合成数据；没有 Steam 连接和游戏客户端，不能作为八名真人验收。

## 固定上游

使用 [SkyeShade/HellForge](https://github.com/SkyeShade/HellForge/tree/a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa)，commit `a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa`，engine `0.1.28`。该提交公开了引擎源码，旧版“引擎闭源”的网页摘要已不适用。构建脚本拒绝不同 commit、修改过的上游源码、指纹不符的 SDK 或编译器。

上游源代码保存在忽略的 `work/hellforge_upstream_20261025/`，不整体复制进本项目。SDK 为 MIT-0；引擎为 GPL-3.0，并有 Mod 例外。原文保存在 `licenses/`；测试引用上游后端，不把后端二进制装进 Mod ZIP。

## 离线重建

需要 Python 3.12、.NET 10 SDK、Git，以及固定 Zig 0.17.0。模板重建核对还使用 `native-storage.lock.json` 固定的 Capstone 5.0.7，当前工作区沿用 `eight_player_candidate_20260927/.native-test-deps`；完整引擎测试另需 Unicorn 2.1.4。以下只处理源码和本项目产物，不寻找游戏安装：

```powershell
git clone https://github.com/SkyeShade/HellForge.git work/hellforge_upstream_20261025
git -C work/hellforge_upstream_20261025 checkout --detach a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa
```

如果该 checkout 已存在，先核对其版本与改动，不覆盖它。下载 `upstream.lock.json` 的 `zig.url` 到新的工具目录，核对 `archive_sha256` 后解压；脚本也会核对 `zig.exe` 的 SHA-256。当前工作区可直接使用：

```powershell
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path (Get-Location) 'work/hellforge-zig-cache'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path (Get-Location) 'work/hellforge-zig-local-cache'
$env:DOTNET_CLI_HOME=Join-Path (Get-Location) 'work/hellforge-dotnet-home'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1'
py -3.12 -B hellforge_multiplayer/tools/build_offline.py `
  --upstream work/hellforge_upstream_20261025 `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

产物在 `build/`：`ep_hellforge.dll`、`adapter_test.exe`、`eight-player-research-hellforge-0.1.0-source.zip`。这些产物被 Git 忽略，可从源码重建。ZIP 只带清单与 `src/`；HellForge 按标准源码 Mod 流程自行编译。DLL 只在本项目的模拟测试进程中加载过。

八槽存储布局、所有者租约、身份票据、4 KiB 读取器预算及证据边界见 [NATIVE_STORAGE.zh-CN.md](NATIVE_STORAGE.zh-CN.md)。该读取器目前不会由 Mod 初始化调用。八端原生属性数据到接收名册的后续验证见 [NATIVE_SYNC.zh-CN.md](NATIVE_SYNC.zh-CN.md)。

原生玩家读取扩展的契约、MinHook 准备和独立重建命令见 [engine/README.zh-CN.md](engine/README.zh-CN.md)。该补丁只改变加载器读取路径；原位玩家数组仍最多四项，独立计分/customization 四槽限制仍保留。

属性发送和接收候选已加入各自的 [Windows x64 栈回溯资料](NATIVE_UNWIND.zh-CN.md)，修正拒绝跳转被当作尾调用的问题，并将接收端的条件寄存器保存移至入口。发送端 12 个场景的 1,308 个指令上下文、接收端 17 个场景的 1,313 个指令上下文通过真实 Windows 回溯接口验证；八端转发测试同时使用两份新候选。保存证据中的五段原异常资料已核对，并作为两个生成器的强制前置检查；10 项来源测试和原捕获重放通过。其他候选的回溯、运行期有效异常表核对、生产 hook 安装和游戏内验证仍未完成。


新增 [四数组共用搬移器](NATIVE_MOVER.zh-CN.md)：C++ 生成 612-byte 完整映像并接入 READY 准备，100 次功能执行和 8,231 个 Windows 回溯上下文通过；保存的三段原回溯资料另核对 92 bytes。插入/删除/重新加入及八端插入夹具已改用其 C++ 输出。搬移现已加入 [十七入口共同开关](ROSTER_GROUP.zh-CN.md)，生产写入排除和剩余入口审计仍待接入。

[四个玩家记录插入入口](NATIVE_INSERT.zh-CN.md) 已沿用原 prologue 构造两段回溯映像，并将完整搬移器范围纳入地址检查。C++ 插入与搬移现在共同参与八笔存储和八端同步；移除和分类也已具备独立映像与读取连接，已定位的十七个入口现有共同发布实现，生产写入排除与完整容量事务仍待实现。

[两个分类入口](NATIVE_CLASSIFY.zh-CN.md) 保留原 prefix/dense 语义，规范化暂存栈和条件寄存器保存，并按完整帧基址生成回溯资料。八笔记录在 enter/leave 重排后交给实际 HellForge 读取器，身份与网络索引保持一致。分类本身不等于加入/离队，辅助分配失败回滚、caller flag/通知、真实身份和生产激活尚未证明。

## 后续实机步骤：尚未执行

原生代码的会话所有权已接上真实 HellForge hook 链并完成离线验证，见 [SESSION_CODE.zh-CN.md](SESSION_CODE.zh-CN.md)。五个合成 hook 验证排序、后续指针更新、发布失败保留及 DLL 固定；实际游戏候选仅注册和查找，没有在宿主上执行。[进程内生成/重定位](PROPERTY_IMAGES.zh-CN.md) 已连接到实际分配与封存；[成组入口](PROPERTY_GROUP.zh-CN.md) 已完成默认转发与受约束的共同开关。真实暂停/排空 guard、完整容量事务、数据回滚及真实数据所有者仍待接入。

1. 先完成交接说明列出的玩家容器和 provider 适配，评估是否已适合实机测试。
2. 由用户明确授权 HellForge 安装路径、安装/启用范围和本次运行测试内容。旧 PID、旧采样额度和此前 GitHub 上传授权都不能代替这次授权。
3. 经授权后，在双方合法安装的相同 HellForge 版本中导入相同源码包，核对 gameplay modlist；源码包的移除对应停用并移除该 Mod，不移除 HellForge 或其档案。
4. 先验证单人加载与两人生命周期，再验证第五人，最后八名真人完整任务。当前包只观察 SDK 事件，不预期产生第五个玩家槽位。

本轮没有安装、启动、检查或读取游戏。旧 64 KiB 采样约束仍保留在历史路线中；没有新的采样授权。
