# 四个玩家记录插入入口的原生生成与回溯

2026-10-25。固定游戏构建 25480438、HellForge SDK 13。`mod/src/ep_insert_image.*` 将四个已有插入候选接入研究 Mod 的 C++ 生成、重定位和 READY 准备流程。它们与 C++ 共用搬移器一起参与存储和八端同步夹具；生产共同开关及真实接纳尚未接入。

## 入口与存储契约

`EpInsertAddresses` 显式输入游戏基址、候选代码地址、原名册 S、完整 B 存储、共用搬移代码和外部拒绝地址。`ep_insert_image_build` 的 kind 必须为 1～4；纯生成只处理数值，不解引用这些地址。

| kind / 名称 | 原 RVA | 原调用输入 | 代码 / 完整映像 bytes |
|---|---|---|---:|
| 1 / dense_legacy | 0x60CA80 | RDX=entity，R8=flags pointer | 597 / 640 |
| 2 / append_legacy | 0x60CBA0 | RDX=entity | 502 / 540 |
| 3 / append_registered | 0x540850 | RCX=entity | 505 / 544 |
| 4 / dense_registered | 0x540920 | RCX=entity，RDX=flags pointer | 596 / 636 |

四者从 global `game+0x3326468` 取得 S；T/D/P 分别为 S+0x80/+0x84/+0x88。B 使用 [共用搬移器](NATIVE_MOVER.zh-CN.md) 的 0x680-byte 四数组布局。14 处数组写入使用 B，计数与映射仍使用 S。每个入口独立增加 T，不能把四者串成同一次加入。

追加入口选择 ordinal=T、初始化主/辅助记录并写入实体指针，原 map helper 成功路径后才增加 T；D/P 不变。密集入口按 flags 选择 D 或 P，必要时调用搬移器，把 P 的记录移至 D，然后按原顺序更新计数、指针和映射。网络属性的初始化由后续发送/接收流程负责；这一步不能当作角色已经创建。

144-byte 无栈前段先核对 S 绑定、T<8、P≤D≤T；密集入口还要求 D==T。失败在任何 prologue、数组或 map 写入前跳到拒绝出口，R10D 原因依次为绑定不符、容量已满、计数顺序错误、密集插入仍有待整理尾端。生产拒绝 handler 必须终止上游操作，目前没有实现。

密集入口的 D==T 是保守前提，真实 caller 是否总满足尚未证明。有效 map backing、新的非 sentinel entity ID、可用 bucket 和覆盖整次操作的并发写入排除仍由调用者保证。原 map helper 对损坏、重复或满表输入的部分写入恢复未补齐，不能把生成器的地址检查当作完整事务保证。

## 映像范围、来源和准备

生成器检查低 canonical 地址、游戏/代码/S/B/搬移器对齐、B-0xE8 不下溢，以及已知区间互斥。检查覆盖本入口完整映像、S、B、拒绝出口、**完整 612-byte 搬移器映像**、global、map helper、原搬移器和四个原插入入口。所有外部 relative jump/call 与 global 访问重新定位，超出 signed rel32 范围时清零输出并拒绝。

已知区间检查不代表任意外部组件均已列入，也不验证搬移器地址处的实际内容或其 S/B 绑定。跨入口、所有代码分配及身份一致性还需要共同发布者验证。旧 Python bundle 仍按代码长度计算部分范围，不能作为新完整映像的生产分配依据。

`native-insert.lock.json` 固定四个原函数、保存捕获、异常资料、证据和既有测试指纹。保存的四条 RUNTIME_FUNCTION 及其 UNWIND_INFO 共 **88 bytes**，逐字节重放通过；无链式片段或语言层 handler。保存 PE 头指向的异常目录未完整捕获，运行期有效异常表仍未确认。

新代码保留原 prologue 和 epilogue。每份完整映像登记两个互不重叠的函数范围：前 144 bytes 使用无栈回溯资料，后半部分直接使用固定来源中的原回溯资料。密集入口原 prologue 为保存 RBX、PUSH RDI、分配 0x20-byte 栈；追加入口为 PUSH RBX、分配 0x20-byte 栈。主体起点作为各自回溯偏移基准。

`ep_insert_code_prepare` 按实际分配地址生成，封为 RX 并登记两条函数表记录，成功返回 READY。未发布时可以取消；生成或保护失败会清理，清理失败保留句柄供重试。Mod 初始化不调用该接口，也没有自动安装入口或修改容量。运行时的生成器不依赖 Python；Python 仅用于离线重建和独立比对。

## 验证与复现

`evidence/native-insert-validation.json` 固定独立测试源码、生成器、模板、捕获来源和测试产物；总引擎收据交叉固定其 SHA-256。

| 验证 | 结果 |
|---|---|
| 既有功能测试 | 9 个方法、515 次执行：432 次四入口候选夹具执行、80 次原四槽对照、3 次关联属性链执行 |
| 插入行为 | 两种 ABI 的全部有效计数分段、密集 prefix/flags、原始内存写入语义、寄存器和栈恢复；连续插入八笔后第九笔写入前拒绝 |
| 完整映像 C++/Python 比对 | 58 组有效地址一致；230 组非法地址拒绝且输出清零，包含旧 545-byte 范围之外的搬移器尾端交叠 |
| API 与来源 | 11 项空参数/非法 kind 检查；8 项来源指纹/原 handler 拒绝检查 |
| Windows 回溯 | 27,171 个候选指令上下文，规范化合成返回地址后去重为 660 组，全部通过；四份人为破坏的回溯资料均被负面对照拒绝 |
| 实际准备与释放 | 四种入口各 27 项，共 108 项通过；含两段函数查找、RX、保护失败、释放失败重试和无自动 hook |

回溯去重按完整指令偏移、RSP、非易失寄存器与 256-byte 栈窗口逐字节比较，没有抽样丢弃不同状态。候选函数仅在 Unicorn 合成地址空间执行；Windows 自有进程只登记映像、查找函数和运行回溯 API。人为破坏的对照不是原游戏函数缺陷。

存储夹具的八笔插入、删除后重新加入，以及八端同步的 64 次插入均改用 C++ 插入与搬移代码。[两个移除入口](NATIVE_REMOVE.zh-CN.md) 已改用 C++ 输出并加入存储夹具；[两个分类入口](NATIVE_CLASSIFY.zh-CN.md) 另外验证 enter/leave 三阶段的实际读取连接，临时资源辅助函数仍是契约替身。来源身份、peer/lifecycle、真实接纳和完整游戏封包仍由各夹具明示其合成边界。

完整重建使用 [引擎离线构建入口](engine/README.zh-CN.md#重建与证据)，自动先编译本项目的测试 DLL，再执行四入口与全部存储/同步验证。已有本次测试 DLL 时可单独运行：

```powershell
py -3.12 -B hellforge_multiplayer/tools/validate_insert_images.py `
  --library hellforge_multiplayer/build/property_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

模板默认只核对；审查过来源变化后，显式运行 `tools/generate_insert_templates.py --write` 才能更新头文件。研究源码 ZIP 包含这三个新增 C++ 源码/头文件，但它仍不具备可玩的八人容量。

## 下一步

已准备的插入、分类、移除、搬移和属性三入口现进入 [十五入口组](ROSTER_GROUP.zh-CN.md)，仍需继续迁移其余读写入口，并落实生产旧路由排空和共同切换。必须同时落实真正覆盖写入者的所有者租约、权威身份票据、临时资源失败契约、运行期来源/ABI/异常表核对、拒绝处理、完整容量事务及激活后的数据回滚。

第 5～8 名角色创建/控制、任务复制、计分/customization 四槽边界和八个独立账号完整任务仍待完成。保持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`；本轮没有安装、启动、检查或读取游戏，旧一次 v2 采样额度仍为零。
