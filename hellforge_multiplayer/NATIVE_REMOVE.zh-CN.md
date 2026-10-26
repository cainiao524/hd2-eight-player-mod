# 两个玩家记录移除入口的原生生成与回溯

2026-10-25。固定游戏构建 25480438、HellForge SDK 13。`mod/src/ep_remove_image.*` 将 legacy 与 registered 两种移除候选加入 C++ 生成、重定位和 READY 准备流程。候选保留完整 prefix/dense/pending 分段压实规则；存储夹具执行移除后重新插入。生产共同开关、真实离队及角色清理尚未接入。

## 行为与存储契约

两种入口共享显式的游戏基址、代码地址、S 管理器、B 八槽存储、共用搬移器和拒绝出口。没有扫描、读取游戏或自动发现地址。原入口分别为 RVA `0x60CEA0`（172 bytes）和 `0x540A40`（160 bytes），使用原 map 删除 helper `0x172F8A0`（259 bytes）。

448-byte 检查前段保存 RCX/RDX/R8/R9/RBX/RSI/RDI，先核对绑定、1≤T≤8、P≤D≤T、map 容量 8、非 sentinel 且存在的 ID、ordinal<T、实体指针对应的 ID 和密集区 prefix 标志。失败恢复寄存器与栈后跳至外部拒绝出口，R10D 保留失败原因；生产拒绝 handler 仍需由统一调用契约提供。

成功路径沿用原删除顺序，再修复扩容后可能存在的 pending 尾段：移除密集成员后若 newD<newT，将原最后一条 pending 记录移至 newD。搬移同步维护四数组与 entity→ordinal 映射，避免留下失效索引或覆盖幸存成员。与当前密集插入入口的 D==T 前提不同，移除覆盖全部有效 P≤D≤T 分段。

这些检查要求 map backing、实体和指针可读，且调用者持有覆盖整次操作的写入排除。它不提供任意损坏指针的安全解引用、并发事务、真实网络身份或游戏实体销毁；已保存的 helper 也未转成可回滚事务。

## 栈和回溯修正

原候选有两种不满足新回溯契约的路径：拒绝分支先恢复栈，再写入 R10D，导致 Windows 无法把后段识别为完整退出序列；pending 修复临时 PUSH RAX 并额外分配栈空间，原主体回溯资料未描述这个深度变化。

新候选将失败原因写入移到恢复序列前，并把额外搬移的 RAX 暂存到 `[rsp+0x38]`，即入口 RSP+0x10 的调用者第二个 home slot。该位置避开 legacy 保存的 RBX，也位于嵌套 mover 的 shadow space 之外。主体栈深度保持原值；代码长度、原 prologue 和既有分支位置保持一致。

检查前段独立登记 20-byte UNWIND_INFO：三个非易失寄存器保存、四个易失参数对应的 8-byte 栈分配。主体独立使用逐字节核对后的原回溯资料。每个映像含两条 RUNTIME_FUNCTION，覆盖检查前段和主体。

| 入口 | 代码 bytes | 完整映像 bytes | 前段 UW 偏移 | 主体 UW 偏移 | 函数表偏移 | 重定位项 |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 717 | 776 | 720 | 740 | 752 | 18 |
| registered | 705 | 760 | 708 | 728 | 736 | 18 |

`native-remove.lock.json` 固定两段原函数、保存证据及原表来源。两条原 RUNTIME_FUNCTION 与两段 UNWIND_INFO 共 44 bytes，未发现链式或语言层 handler；游戏运行期有效异常目录仍待授权后的验证。

## 完整映像与准备

生成器检查低 canonical 地址、各地址对齐、B-0xE8 不下溢和已知区间互斥，覆盖自己的完整映像、S、B、拒绝出口、完整 612-byte mover、global、map 删除 helper、原 mover 和两个原移除入口。外部调用、跳转和 global 访问超出 signed rel32 范围时拒绝，并清零输出。

`ep_remove_code_prepare` 按实际分配基址生成，封存 RX 并登记两段函数表；成功只达到 READY。失败执行未发布清理；清理失败保留可重试句柄。它不会发布 hook、激活八人容量或寻找游戏。其他入口的分配、身份及绑定一致性仍须由共同发布者验证。

## 离线验证与重建

功能、回溯、边界和准备生命周期的逐项结果保存在 [验证收据](evidence/native-remove-validation.json)。

| 检查 | 实际结果 |
|---|---|
| 既有功能套件 | 9 个方法、2,293 次执行；包括 152 次原四槽对照，以及候选和关联链路执行 |
| 分段压实 | 两种 ABI 的全部有效八槽分段与移除位置，空槽/错误 ID/计数/容量/映射拒绝，连续移除、重新插入及属性索引检查 |
| C++ 完整映像 | 22 组有效输入逐字节一致；122 组无效输入拒绝并清零，包含 mover 尾端与本映像元数据交叠 |
| 参数和来源 | 7 项空参数/非法 kind，4 项来源身份/handler 拒绝检查 |
| 准备生命周期 | 54 项实际分配、RX 封存、函数表登记、未发布释放及失败重试检查 |
| Windows 回溯 | 250,020 个候选指令状态，逐字节去重为 4,670 组，全部恢复原 RIP/RSP 和八个非易失寄存器；四个旧路径负对照均复现失败 |

去重覆盖指令偏移、栈深度、非易失寄存器和 256-byte 栈窗口，未抽样丢弃不同状态。功能体只在 Unicorn 的合成地址空间运行；Windows 自有测试进程只登记映像并调用回溯 API。原候选负对照使用相同的新回溯表，验证上述两种旧路径与该表不兼容，不表示原游戏函数本身有这些缺陷。

存储夹具现执行 C++ 生成的插入、搬移和移除代码，随后把八人、移除后七人、重新插入后八人的三份映像交给实际 HellForge 读取器。八端属性同步夹具尚未包含离队或重新加入协议；不能把这两组证据合并解释为真实八端生命周期已完成。

完整重建见 [引擎离线构建入口](engine/README.zh-CN.md#重建与证据)。已有本次测试 DLL 时可单独执行：

```powershell
py -3.12 -B hellforge_multiplayer/tools/validate_remove_images.py `
  --library hellforge_multiplayer/build/property_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

模板默认只核对，显式 `tools/generate_remove_templates.py --write` 才会更新。旧 Python bundle 的代码长度不能作为新完整映像的生产分配依据。

## 剩余工作

[分类](NATIVE_CLASSIFY.zh-CN.md) 现已具备 C++ 生成、READY 准备和独立存储读取验证。插入、分类、移除、搬移和属性三入口已加入 [十四入口组](ROSTER_GROUP.zh-CN.md)。继续迁移其余读写者，并落实生产排空和切换。落实写入者所有权、权威身份票据、临时资源失败契约、运行期来源/ABI/异常表验证、外部拒绝处理、完整容量事务和激活后的回滚，再接入角色创建/控制、复制、死亡增援和任务结算。

保持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。本轮没有安装、启动、检查或读取游戏，旧 PID 30776 的一次 v2 采样额度仍为零。八名真人、八个独立账号完成同一任务仍是最终验收条件。
