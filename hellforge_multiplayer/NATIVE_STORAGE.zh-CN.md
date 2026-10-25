# 原生八槽存储到 HellForge 读取者

2026-10-25，游戏 build 25480438，SDK 13。当前连接已通过离线验证；[存储所有者](ROSTER_OWNER.zh-CN.md) 已实现并连接离线消费者，生产写入覆盖、底层复制与身份来源仍未绑定。研究 Mod 的初始化不会注册此 provider，也不会调用这里的读取入口。

## 已实现的连接

`mod/src/ep_native_roster.cpp` 将旧原生候选生成的四数组存储解码成私有 `EpHfRosterSnapshot`。`ep_native_roster_read` 可直接作为 `EpHfRosterProvider.read`；绑定容量必须为 8。`ep_roster_api.h` 与引擎补丁中的接口头逐字节相同，构建时核对指纹。

保留原管理器地址 S 和计数/索引表，四个数组移到独立的 B；B 必须 16 字节对齐，共 0x680（1,664）字节。这里的 ordinal 是数组位置，不能当作网络索引。

| 数据 | 地址/布局 | 读取用途 |
|---|---|---|
| 管理器绑定 | game + 0x3326468 | 读取前后核对 S |
| tracked / dense / prefix | S + 0x80 / 0x84 / 0x88 | 验证 prefix ≤ dense ≤ tracked ≤ 8 |
| entity → ordinal 表 | S + 0xD0 指针，+0xD8 容量，+0xDC 空键，+0xE0 乘数 | 按原生线性探测算法核对身份位置；容量限定 8 |
| descriptor 指针 | B + 8 × ordinal | descriptor + 8 为 player entity ID |
| primary | B + 0x40，步长 0x70 | 保留布局；读取器不从此处猜网络索引 |
| auxiliary | B + 0x3C0，步长 0x38 | +0 是 peer，+0x18 是 lifecycle |
| property | B + 0x580，步长 0x20 | +0 是 avatar network ID，+0xC 是 player network index |
| 本地身份 | [game + 0x347CEF0] + 0xB398 | 与 peer 比较，产生 local 标记 |

avatar network ID、player entity ID、peer、network index 和 ordinal 各自保留含义。avatar entity 留给 HellForge 原有解析路径处理。generation 不存在于这些数组中，由外部所有者提供的票据核验，不能从位置、生成事件次数或生命周期值推算。

## 所有者必须提供的契约

`EpNativeRosterSource` 需要以下契约。新增 `ep_roster_owner.*` 实现持锁的 begin/read/end 适配，读写共同使用 `mutate`；底层内存复制、权威票据及游戏写入入口还需生产集成：

1. `begin` 同时保留所有者寿命并排除本次读取期间的写入，返回 S、B、构建号、epoch 和最多八份身份票据。只有引用计数不够；必须防止四个数组、索引表、计数及票据在读取中途变化。失败时不得遗留租约。
2. `read` 仅在有效租约内复制指定范围，失败明确返回 0。这里没有进程查找、地址扫描、内存分配、安装、注入或写入代码。
3. `end` 在每次成功 begin 后执行，包括中途失败；回调不能抛异常或递归调用 provider。解绑完成后才可释放 source、context 和代码，停止游戏侧写入及恢复原存储另有事务要求。

票据包含 peer、player entity、权威 network index、非零 generation 和一致 epoch。重复身份/索引、过期票据、错误 build、错误指针对齐、存储区重叠、超过八项、映射错误或读取失败都会拒绝快照，输出保持全零。

当前仅在 dense == tracked 时输出名册；存在待完成的成员时返回 `EP_NATIVE_PENDING`。这会暂时使消费者不可用，避免把“已创建一人、仍待创建多人”当作单人。完整 pending 加入期间的可用性策略仍待实现，不能将此行为描述为完整接纳支持。

读取器对自身经 `read` 发出的请求设 **4,096 字节上限**；八成员样本实际请求 2,024 字节。该限制不计外部 begin/end 的内部工作，也不是整个游戏会话的累计预算。它与历史一次性 **64 KiB** 采样授权不同，不产生新的游戏访问授权。

## 这次验证实际执行了什么

`tools/native_roster_fixture.py` 先校验 `native-storage.lock.json` 中旧代码和保存证据的指纹，再使用 Unicorn 执行 C++ 生成的[插入](NATIVE_INSERT.zh-CN.md)、[移除](NATIVE_REMOVE.zh-CN.md)、[共用搬移器](NATIVE_MOVER.zh-CN.md)和保存的原生哈希表辅助代码。独立运行夹具须提供 `--property-library`，总构建已自动传入。它导出三个合成内存映像：

- 从空名册完成八次插入；第九次在写入前被拒绝。
- 删除 ordinal 4，原 ordinal 7 被移动到 4，人数为 7。
- 将被删除的 descriptor 重新插入末尾，人数恢复为 8。

随后 `tests/native_roster_test.c` 将这些映像交给本次读取器，再绑定到实际补丁后的 HellForge loader，调用 `EpRosterRead`、`PollPlayers` 和 `ActPlayerCount`。验证移动后的 peer 仍保留 network index 7；重新插入的 peer 位于 ordinal 7，但 network index 为 6。重排不产生额外生成事件；票据代次更新后的重新加入产生一次生成事件。

**589 次断言通过**，其中包括每次内存复制的租约检查、逐次读取故障、无效数据、离开压缩和重新插入。它不是 589 个独立场景。原有引擎消费者测试另有 100 次检查；适配器 26 次、上游后端 132 次检查保持通过。

原生执行产生了 descriptor 指针、三个计数、entity→ordinal 映射和部分数组初始化/搬移。descriptor/实体编号、prefix 标志、peer、lifecycle、property 值、本地身份和 generation 票据是明确构造的测试输入。重新插入后的 peer/property 也由测试补入。因此这条链路仍不能证明真实接纳、角色分配、复制生产者或增援已完成。

后续 [八端原生属性转发验证](NATIVE_SYNC.zh-CN.md) 已将独立属性样本改为由发送/接收候选执行产生，并经过 HellForge 后端。它保留本节三映像用例，同时新增八份不同布局；游戏完整封包、实体分派和真实接纳仍未执行。

插入与重新插入现使用 [四入口 C++ 生成器](NATIVE_INSERT.zh-CN.md)，共用搬移和[移除本体](NATIVE_REMOVE.zh-CN.md)也来自 C++；完整映像先与固定 Python 参考比对。存储契约和上述合成输入边界保持不变。

[分类连接](NATIVE_CLASSIFY.zh-CN.md) 另有三份映像与 359 次断言：八笔记录按 P=2→3→2 执行 C++ enter/leave，实际读取器维持 peer、network index/ID、generation 和本地身份，重排不增加生成事件。T/D 始终为 8；分类不代表真实接纳或离队。临时资源辅助函数、caller flag 与身份票据仍由夹具提供，完整失败回滚及生产写入排除尚未实现。

## 重建与下一步

运行 [引擎重建命令](engine/README.zh-CN.md#重建与证据)，会同时重建和执行这组测试。除固定 Zig、MinHook、上游源码外，Python 3.12 需要 `unicorn==2.1.4` 和 `capstone==5.0.7`；现有依赖位于被忽略的 `eight_player_candidate_20260927/.native-test-deps/`。新环境可安装到该目录，构建会校验版本：

```powershell
py -3.12 -m pip install --target eight_player_candidate_20260927/.native-test-deps unicorn==2.1.4 capstone==5.0.7
```

该命令只用于尚未准备依赖的新环境，不覆盖现有环境。收据在 `evidence/engine-roster-validation.json`；三个映像、测试程序及研究 DLL 位于被忽略的 `build/`。

下一步将 [存储所有者](ROSTER_OWNER.zh-CN.md) 接入原生写入入口与旧调用排空，明确谁产生 peer/property 和代次票据、谁安装/撤销存储生产者，再处理计分、customization、角色资源及复制的独立四槽限制。生产绑定、真实存储扩容、安装整合和真人任务验收目前均未通过。本轮没有启动、检查、读取或修改游戏。
