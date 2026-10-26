# HellForge 私有玩家读取扩展 v1

适用上游 commit：`a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa`，SDK 13、engine 0.1.28、游戏 build 25480438。

这份补丁让 HellForge 原生读取者可以消费外部提供的玩家快照。它没有扩大游戏里的玩家资源、创建角色、放宽接纳或修改复制容量；当前研究 Mod 也不会自动绑定这个接口。B 布局读取回调已在 Mod 源码中实现，但生产环境的存储所有者与绑定尚未实现，不能安装后期待出现第五人。

## 修改范围

- `hellforge_modloader.c` 引入 `ep_roster.c`，并在 Mod 初始化失败时撤销其绑定。
- `event_sources.c::PollPlayers` 使用共同快照；按 peer、代次、会话 epoch 和绑定租约识别生命周期。
- `event_polls.c::EvpPlayers` 使用共同快照；治疗、统计、武器以及调用该函数的动作消费者使用同一格式。观察缓存区分会话和绑定，避免跨会话误报治疗。
- `passives.c::PassivesLocal` 从共同快照选本地玩家并取得人数；原有“仅单人覆盖”判断能够看到八人。独立的四条 customization 记录检查保留。
- 原版玩家数组始终最多读四项。`EVT_MAX_PLAYERS` 的 16 只控制加载器自身缓冲区；第五项原位读会撞上 avatar 网络表，所以没有扩大原位读取。

计分记录的 `index < 4`、customization 的 `PSV_RECORDS=4`、游戏角色资源与复制结构仍是后续工作。16 是继承旧核心的硬边界；最终产品目标是八人，提供者可声明 capacity=8，超过它的快照被拒绝。

## 提供者契约

从补丁后的 loader 动态解析 `hellforge_ep_roster_api_v1`，核对 magic、size、version 和 limit。类型声明随补丁的 `native/mod-loader/ep_roster.h` 提供；使用 `EpHfGetRosterApi` 调用查询函数。这是本项目私有接口，没有改变 SDK 13，也没有宣称是官方 SDK 14。

1. 只允许已登记且处于加载状态的 `HfMod*` 绑定；上游在调用 init 前设置 loaded，所以 init 中可以注册。仅一个提供者，第二个不能替换现有绑定。返回非零租约才算成功。
2. 回调在游戏线程或 watch 线程同步执行，必须线程安全并返回一致的值快照。epoch 非零，在会话或所有者更换时改变；slot generation 非零，在同一身份重新创建时改变。它们由真实存储的生命周期产生，不能用事件计数猜测。
3. 每项给出 peer、player entity、avatar entity、生命周期、本地标记、权威 network_index 和 generation。列表顺序可以改变，稀疏索引不会被压成连续槽位。avatar 的 network_id 与玩家 network_index 含义不同；直接提供 avatar 时使用 `network_id=0x7FFF`。
4. epoch、容量、数量、重复 peer、重复索引、重复非零实体、本地玩家歧义、保留字段均检查。没有本地玩家可以表示尚未创建；多个本地玩家拒绝。`binding` 由加载器写入，提供者必须填零。
5. 提供者已绑定但返回不可用、快照无效或 Mod 已失效时，读取返回不可用，不回退四人原版视图。零成员快照是有效结果。
6. 解绑必须携带同一 owner 和租约；过期租约不能解绑新提供者。解绑等待在途回调完成，返回后才能释放 context 和提供者代码。不要持有回调需要的锁调用解绑；回调不得递归调用本接口，递归被拒绝。发生 native owner 迁移时，还必须先停止其写入并完成自身 lease 清理，本扩展不能替代 Bridge 的资源事务。
7. 初始化失败路径会清除绑定。显式解绑以后原版四人读取恢复，因此真实扩容撤销必须先恢复或隔离游戏侧状态；单独解绑读取接口不是完整回滚。

## 重建与证据

准备 `upstream.lock.json` 固定的未修改上游源码和 Zig，再下载 `engine/patch.lock.json` 指定的 MinHook 1.3.4 ZIP，核对 archive SHA-256 后解压到工具目录。构建脚本还会逐项验证 MinHook 源码，不运行其安装程序。

```powershell
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path (Get-Location) 'work/hellforge-zig-cache'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path (Get-Location) 'work/hellforge-zig-local-cache'
$env:DOTNET_CLI_HOME=Join-Path (Get-Location) 'work/hellforge-dotnet-home'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1'
py -3.12 -B hellforge_multiplayer/tools/build_engine_offline.py `
  --upstream work/hellforge_upstream_20261025 `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe `
  --minhook work/hellforge_toolchain_20261025/minhook-1.3.4
```

新增存储测试还需要 Unicorn 2.1.4 和 Capstone 5.0.7；依赖位置、准备命令及原生代码/合成输入的界限见 [NATIVE_STORAGE.zh-CN.md](../NATIVE_STORAGE.zh-CN.md)。

脚本从固定 Git 对象导出新源码目录，检查并应用补丁，验证六个修改文件的指纹，再编译原生 loader 与测试。原上游 checkout 保持原样；导出目录保留在被忽略的 `build/engine-source-*`，不会重置或删除旧工作。

测试直接包含补丁后的 `hellforge_modloader.c`，调用实际枚举、事件、治疗和被动效果读取函数。合成数据只在本测试进程内；构建出的 DLL 仅用来核对私有导出，没有调用 `hellforge_loader_start`。测试不运行 watch、安装 hook、修改被动效果或执行游戏动作。

结果记录在 `evidence/engine-roster-validation.json`：100 项检查，含八人读取、第八人事件、代次/epoch/绑定变化、重排/离开、稀疏索引、十六项硬上限、八容量拒绝第九项、无效数据不回退、单人判断、原位四槽边界、初始化失败清理和并发解绑等待。产物为 `build/hellforge_modloader-research.dll` 和 `build/engine_roster_test.exe`，均保持本地且不作为可安装发布物。

同一入口还执行新增的 `native_roster_test.exe`：589 次断言，将原生候选实际写出的八槽映像连接到本次 B 布局读取器，再交给实际消费者。覆盖插入、删除压缩、重新插入、权威索引保持和逐次读取故障。三个映像及其来源/输入边界另列在同一收据的 `native_storage_fixture`。该数量包括每次租约/复制检查，不是独立场景数。

入口还会运行 [八端原生属性转发链路](../NATIVE_SYNC.zh-CN.md)，需要 .NET 10 SDK。结果为后端集成模式 264 次检查、56 次原生接收、1,678 次消费者断言；该链路用显式测试桥接代替完整游戏封包和实体分派，不能作为八人实机同步证据。

补丁按 HellForge 引擎的 GPL-3.0 条款维护；原文及 Mod 例外保存在 `licenses/`。MinHook 许可证同目录保留。完整 loader 仍需要对应上游源码，这份 patch 不替代它的源代码义务。

构建入口同时运行 [四个插入入口](../NATIVE_INSERT.zh-CN.md)：515 次功能执行、660 组不同回溯状态、108 项实际准备检查，以及 88 bytes 原元数据重放。插入和搬移的 C++ 输出共同进入存储/同步夹具；单独收据 `native-insert-validation.json` 的指纹写入总引擎收据。生产自动绑定和共同切换仍未实现。

同一入口还构建 [两个移除入口](../NATIVE_REMOVE.zh-CN.md)：2,293 次功能执行、4,670 组不同 Windows 回溯状态、54 项准备生命周期检查和 44 bytes 原元数据重放。四个旧候选负对照复现拒绝/额外搬移的栈契约问题。插入、移除和搬移的 C++ 输出共同进入三映像存储夹具；`native-remove-validation.json` 交叉固定于总收据。八端同步测试尚未包含离队协议，生产移除/实体清理没有接入。

同一入口另构建 [两个分类入口](../NATIVE_CLASSIFY.zh-CN.md)：853 次功能执行、20,905 组不同 Windows 回溯状态、54 项准备检查和 192 bytes 原元数据重放。`native-classify-validation.json` 固定于总收据；`native_classify_roster_test.exe` 使用三个新存储映像完成 359 次实际读取断言，保留身份、网络索引和生成事件数。临时资源辅助函数、caller flag 及身份票据仍为合成契约，生产分类及分配失败回滚未接入。

完整构建还自动运行 [原生发送与接收候选的 Windows 栈回溯验证](../NATIVE_UNWIND.zh-CN.md)：发送端 1,308 个、接收端 1,313 个指令上下文通过，对照组分别复现 3 次和 7 次旧拒绝跳转错误。测试仅注册自有不可执行数据映像的函数表，用完后撤销；没有加载或运行游戏。独立收据为 `evidence/native-producer-unwind-validation.json` 与 `evidence/native-receiver-unwind-validation.json`，两者 SHA-256 同时写入总引擎收据。

构建入口先执行 10 项原异常资料来源检查测试，并从仓库已有捕获重放五条函数表记录和相应回溯资料（元数据合计 168 bytes）。每个候选生成器也强制检查来源指纹和无语言处理器条件。来源收据为 `evidence/native-unwind-source-validation.json`，总引擎收据保存其指纹。保存的 PE 头指向另一份未完整捕获的异常目录，故此步骤不代表运行期有效异常表已确认。

构建入口另执行 [会话代码所有权验证](../SESSION_CODE.zh-CN.md)：383 次检查使用真正的 HellForge HookAdd/ApiHookEx 和 MinHook，在测试自身的合成目标上安装五个 hook。验证注册先于发布、下一跳变量稳定且可更新、并发取消拒绝、SDK 失败后的保留，以及独立 DLL 的模块固定。此测试有别于前述 roster 测试：它实际安装自有进程 hook，但没有安装游戏 hook、运行 Watch 或执行游戏候选函数体。测试源码和两个产物均纳入总收据。

入口继续构建和验证 [属性成组入口](../PROPERTY_GROUP.zh-CN.md)：355 次真实链/合成函数体检查，18 组实际入口分支、24 组错误位置拒绝，以及每幅两条函数表下的 7,169 个 Windows 回溯上下文。`property-gate-validation.json` 单独固定输入、产物与参考收据，`engine-roster-validation.json` 交叉记录其指纹，并记录成组测试 DLL/EXE。生产 guard 和激活后数据回滚均明确标为未实现，Mod 初始化没有绑定。

同一入口另构建 [实体到网络索引 getter](../NATIVE_GETTER.zh-CN.md)，核对保存的单段原回溯资料，运行 7 个功能测试、4,548 个 Windows 回溯上下文和 25 项准备生命周期检查。八端接收后增加 64 次原生 getter 查询。单独收据 `native-getter-validation.json` 固定来源和产物，总引擎收据交叉记录其指纹；getter 已接入三入口成组开关，但没有游戏内发布。

同一入口继续构建 [四数组共用搬移器](../NATIVE_MOVER.zh-CN.md)：100 次功能执行、8,231 个 Windows 回溯上下文和 25 项准备生命周期检查，离线重放三段原元数据共 92 bytes。测试 DLL 先于存储夹具构建，三份存储映像与八端插入使用 C++ 搬移代码；独立收据为 `native-mover-validation.json`，总收据交叉固定指纹。搬移器尚未纳入生产共同开关。

完整入口另执行 [十六入口组](../ROSTER_GROUP.zh-CN.md)：`roster-gate-validation.json` 验证十六份实际生成开关和全部已捕获主体回溯状态；96 组分支、167 组非法配置和 49,846 个回溯上下文通过；`roster_group` 在总收据中记录 33 个自有进程场景、15,158 次检查，包括十六个发布位置各自的 SDK 前/后故障。真实 HellForge 链只运行合成 leaf 函数，生产 guard 和激活后数据回滚尚未实现。两个新测试产物及全部来源纳入总收据。

完整入口另构建 [存储所有者](../ROSTER_OWNER.zh-CN.md) 的实际 C++ DLL，并用相同的三份存储夹具连接真实 loader。641 次检查验证读写互斥、revision/票据提交、离队代次保留、旧 provider 失效、关闭排空和结构化异常后的隔离与锁释放。DLL 沿用上游 ModKit 编译选项，不增加 Microsoft 扩展开关。总收据 `roster_owner` 和共同指纹表记录结果及源码、DLL/EXE；真实原生 hook、全体写入者、权威身份和底层复制尚未绑定。

完整入口继续执行 [十六入口受管调用](../ROSTER_CALLS.zh-CN.md)：实际 owner、ABI 桥、SDK/MinHook 链连接自有目标，覆盖六参数、高位整数、浮点/向量返回、全部非易失 GPR/XMM、同 owner 嵌套、真实锁排空和故障隔离。两个静态桥的 76 个指令边界通过实际 PE 表执行 Windows 回溯；原十六函数体的直接堆叠访问另从固定证据核对。48 个新进程场景包括十六种正常/故障模式和十六处 SDK 前/后失败，总收据 `roster_calls` 保存结果、源码及 DLL/EXE/回溯夹具指纹。`roster-call-abi-validation.json` 的 SHA-256 交叉写入总收据；外部辅助函数和实际调用端 ABI、生产 guard、权威身份及真实游戏绑定仍未证明。

新增 [原生注册表与关联查询](../NATIVE_REGISTRY.zh-CN.md)：RVA 0xB54E00 与 0x606520 已进入 C++ 生成、实际准备生命周期及十六入口共同所有者。8 个功能测试、87 次执行、63 项 API 检查、45 项准备检查和 3,963 个 Windows 回溯上下文通过；保存的四段原回溯资料重放 140 bytes。tag 73 直接调用同组关联主体，tag 69 使用外部 B 数组；其余 tag 回调仍为契约替身，晚期拒绝不承诺撤销此前副作用。单独证据为 `native-registry-validation.json`；生产自动绑定、游戏访问和八人实机验证仍未完成。

[离队前清理移植](../NATIVE_DEPARTURE.zh-CN.md) 已纳入离线构建及独立 C++ 映像准备验证。它保留十三段来源回溯，新增完整栈和 XMM6 Windows 验证；已接入第 15 个共同入口及同组 getter，尾调用关闭/提交等待与嵌套删除故障另有自有程序验证。第 16 个外层入口已在自有双阶段测试中保护清理返回后的间隙；真实尾调用 ABI、原 dispatcher 全部执行和副作用恢复仍未证明，生产未启用。

同一入口新增 [原实体删除集成执行](../ENTITY_REMOVE_SCOPE.zh-CN.md#原-dispatcher-集成执行)：完整保存的 `FDC820` 在 Unicorn 中真实查询两张回调表，连接 C++ 离队/getter/删除/搬移映像及原注册表删除 helper。19 个场景覆盖四槽对照与第五到第八项记录、分区压实和额外返回数反例；242/373 条原指令实际执行。返回 17 与 `0xFFFFFFFF` 的替身揭示原调用方没有局部数组上限检查，真实提供者的契约仍未核定。总收据 `native_entity_remove_dispatch` 固定独立 `entity-remove-dispatch-validation.json` 的哈希；模拟器与 Windows owner/SDK 链为两套测试，不能合并视为生产实测。
