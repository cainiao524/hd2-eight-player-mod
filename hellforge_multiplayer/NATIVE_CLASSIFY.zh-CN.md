# 玩家分类入口的原生生成、回溯与读取连接

2026-10-25。固定游戏构建 25480438、HellForge SDK 13。`mod/src/ep_classify_image.*` 将 enter/leave 两种分类候选加入 C++ 生成、重定位和 READY 准备流程。分类结果另外交给真实 HellForge 读取器，检查重排后玩家身分和网络索引保持一致；生产发布及游戏内分类尚未接入。

## 保留的行为

这里的 enter/leave 是进入或离开名册的 prefix 分类，不是玩家加入或退出房间。两者保持 T、D 不变，调整 P，并修复 entity→ordinal 映射、指针与相关记录的位置。目标必须位于 dense 范围：enter 的 ordinal≥P，leave 的 ordinal<P，且调用者须已设置目标实体的 bit0。

enter 沿用原始语义：清空 primary[old P]，保留 primary[target]；不能把它描述为四组记录全部按实体交换。leave 的 primary、aux、property 临时搬移也保留原顺序。调用前后的 flag 更新和通知仍由调用者负责。

480-byte 检查前段核对 S 绑定、1≤T≤8、P≤D≤T、八桶映射、非 sentinel 的存在 ID、dense ordinal、分类方向、实体 ID 一致性和 bit0。失败恢复参数、非易失寄存器和入口 RSP，再跳转至显式拒绝地址。有效指针、唯一键/正确探测链和覆盖整次操作的写入排除仍是调用者前提。

## 栈与回溯规范化

旧候选在 enter 的 37 处、leave 的 51 处数组访问旁 PUSH/POP RBP，临时把 RBP 改成 B-0xE8。新版本在同一范围使用 `[rsp+0x18]` 暂存并恢复 RBP，保持主体栈深度不变。所选原指令不引用 RSP、不写 RBP，暂存期间没有调用或跳转；所有直接栈引用也已核对。临时对象从 RSP+0x20 开始，嵌套调用可以覆盖整个 shadow space，但发生调用前 RBP 已恢复。

原 enter 只在部分路径保存 R12，leave 部分保存 R12/R14。新版本在主体入口将它们保存到原 home slot，原条件保存位置改为 NOP，原恢复操作继续保留。这样每个主体只需一份完整回溯描述，所有局部分支和外部引用按新指令位置重新计算。

Windows 的 SAVE_NONVOL 偏移相对当前回溯帧基址。新提前保存记录在完整 prologue 建好后才生效，使用 frame+0x60／0x68；在此前的进入过程里，R12/R14 尚未被修改。离线调试曾在 enter 的 offset 0x1F5 发现入口偏移误用，修正后该中间状态能恢复正确的 R12。拒绝原因写入也移到 POP 序列之前，保持可辨识的退出顺序。

| 入口 | 原 RVA | 代码 bytes | 完整映像 bytes | 主体 UW 偏移 | 函数表偏移 | 重定位项 |
|---|---|---:|---:|---:|---:|---:|
| enter | 0x60CF50 | 2,222 | 2,296 | 2,244 | 2,272 | 60 |
| leave | 0x60D300 | 2,693 | 2,768 | 2,716 | 2,744 | 78 |

每个映像登记检查前段和主体两条 RUNTIME_FUNCTION，分别使用 20-byte 与 28-byte UNWIND_INFO。`native-classify.lock.json` 固定原函数、证据和六段原回溯记录；其中四段有链式记录、均无语言层 handler。保存资料共重放 192 bytes。游戏运行期有效异常目录仍未确认。

## 生成与准备边界

输入为显式游戏基址、代码地址、S、B 和拒绝出口。生成器检查地址、对齐、B-0xE8 下溢、完整映像及已知数据/原函数/三个辅助函数区间互斥，并重定位全部 rel32 与绝对引用；非法输入清零输出并拒绝。

`ep_classify_code_prepare` 按实际分配基址生成、封存 RX 并登记两段函数表，成功只到 READY。未发布失败执行清理，清理失败保留可重试句柄。它没有自动发现游戏、发布 hook 或启用八人容量。跨入口分配、绑定与来源一致性仍由共同发布者负责。

## 验证与读取连接

完整结果见 [分类验证收据](evidence/native-classify-validation.json) 和 [引擎总收据](evidence/engine-roster-validation.json)。功能体在 Unicorn 合成地址空间执行，Windows 自有进程只登记代码映像并运行回溯 API，不直接执行游戏函数体。

| 验证 | 实际结果 |
|---|---|
| 功能 | 7 个测试、853 次执行；其中 70 次固定原函数对照 |
| Windows 回溯 | 268,923 个执行上下文去重为 20,905 组，全部通过；重新引入的四处栈回归均被负对照捕获 |
| 生成边界 | 18 组有效输入逐字节一致，86 组非法输入拒绝并清零；7 项 API 契约、4 项来源破坏检查通过 |
| 准备生命期 | 54 项实际分配、封存、函数表登记和失败清理检查通过 |
| 分类存储读取 | 359 次断言通过，三份映像各读取 2,024 bytes；生成计数维持 8，没有因重排重复生成 |

负对照在新映像中有意重新引入旧的拒绝顺序和一处临时 PUSH/POP，保持代码长度后捕获失败状态；它们不是原游戏函数缺陷的证明。回溯状态按指令偏移、RSP、八个非易失寄存器及完整 256-byte 栈窗口逐字节去重，没有抽样丢弃不同状态。

`native_classify_fixture.py` 构造八笔存储，执行 C++ enter 与 leave 后导出三份映像。peer 顺序依次为 `[0,1,2,3,4,5,6,7]`、`[0,1,7,3,4,5,6,2]`、`[7,1,0,3,4,5,6,2]`，P 为 2→3→2，T/D 保持 8。`native_classify_roster_test.c` 将结果接入实际读取器、PollPlayers 和人数消费者，检查网络索引、网络 ID、generation、本地玩家及生成事件计数。

临时资源的 create/allocate/release 三个函数是**契约替身**：检查调用顺序、尺寸、对齐、shadow space、易失寄存器和临时对象生命期，没有执行保存的辅助函数体。来源候选会在分配前修改部分状态，因此分配失败、重入或交错操作的完整回滚仍未证明。peer、generation、属性初值及 caller flag 也是合成输入。八端属性测试尚未加入分类协议，读取连接不能替代八名真人同步证明。

## 重建与下一步

完整重建见 [引擎构建入口](engine/README.zh-CN.md#重建与证据)。已有本次测试 DLL 时可单独执行：

```powershell
py -3.12 -B hellforge_multiplayer/tools/validate_classify_images.py `
  --library hellforge_multiplayer/build/property_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

模板默认只核对，审查后显式 `tools/generate_classify_templates.py --write` 才会更新。旧 Python bundle 中的代码长度与历史 limits 不代表新完整映像的生产分配或准备状态。

插入、分类、移除、搬移和属性三入口现已通过 [十七入口组](ROSTER_GROUP.zh-CN.md) 统一发布；下一步落实生产写入排除及旧路由排空；补齐临时资源成功/失败契约、调用者 flag/通知、权威身份、拒绝处理和完整容量事务，再继续角色创建、控制、复制与八人任务验收。

保持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。本轮仅使用工作区源码、保存证据和自有测试进程，没有启动、检查、读取或修改游戏；旧一次 v2 采样额度仍为零。
