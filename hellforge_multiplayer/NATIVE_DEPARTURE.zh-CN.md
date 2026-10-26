# 离队前清理函数的 HellForge 移植

2026-10-26。固定 HellForge commit `a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa`、SDK 13、游戏 build 25480438。`0x605950–0x605F2F` 已有 C++ 映像生成和独立准备生命周期；现已作为第 15 个入口接入共同开关及可选受管调用，并绑定同组 getter。本轮只使用保存证据、自有测试程序及模拟内存，没有启动、检查或读取游戏。

## 本次实际完成的范围

`mod/src/ep_departure_image.*` 接收明确的 game/S/B/getter/reject 地址，生成 2,712-byte 完整映像，其中代码为 2,262 bytes，包含 65 处重定位。它先核对 S、目标实体、`P≤D≤T≤8`、八槽 map、ordinal、目标 pointer 及 primary 标记，再执行保存的离队前清理主体。

六处名册数组访问使用八槽 B。原 `6059EE` 调用点改接共享 `606AD0` network-index getter，完整 getter 映像的 388 bytes 纳入地址重叠检查；没有全局替换原 `606820`。原资源清理、关联控制器、注册与队列、间接回调及末端尾调用保留。原 ID 查询与 network index 的含义不混用。

提前通知使用进入时的 `D - (ordinal < D)`。移除 pending 成员不再递减 dense 数量，零 dense 也不下溢。末端通知仍读取当时 S.D；它不被提前预测值替换。这个函数执行离队前清理，真正的 map 删除和数组压实仍在后续函数里，不能仅凭本函数完成就声称离队事务已经结束。

## 完整的 Windows 回溯对应

来源锁保存了 13 段原始 `RUNTIME_FUNCTION` 与完整 chained unwind，均按已保存的捕获数据重放。每段保留各自的条件保存状态，父项重新定位到同一映像较早的记录；没有删除原来的条件式 R12/R15 或 XMM6 保存。加上入口 guard，总共 14 条函数表记录。

主体栈帧从 128 扩至 144 bytes，包含三个 push 后的最深栈位移为 168 bytes。两个预测局部值放在帧内 `+0x60/+0x64`，XMM6 保存移动到 `+0x70`；其余受影响的保存位置及回溯偏移同步调整。原 ALLOC_SMALL 改为缩放 16-bit 形式的 ALLOC_LARGE。每个 unwind code 的指令偏移也根据重定位后的实际边界重算。

拒绝分支先写 R10D 原因，再 POP 和 JMP，避免已恢复栈后插入 MOV 导致 Windows 无法识别尾段。`ep_session_code_seal_table` 现接受最多 15 条独立记录，并增加有界 ALLOC_LARGE 与非易失 XMM6–15 的 SAVE_XMM128 格式支持。重复 metadata、循环或向后续记录引用、语言 handler、截断参数、零 large allocation 与易失 XMM 保存仍拒绝。封存检查结构；指令与 metadata 的对应另由 Windows 上下文测试证明。

## 验证证据

[专用收据](evidence/native-departure-validation.json)记录：

- 7 个原有测试方法、43 次功能执行，包括原四槽对照、第 5～8 个位置、pending/零 dense、关联资源分支、入口拒绝，以及随后真正删除/压实的模拟链。
- C++ 输出逐字节对照 Python 参考，并覆盖 ASLR、参数独立变化、完整映像重叠、非规范地址及 rel32 边界。22 组有效输入与参考一致，85 组无效输入均拒绝。
- 52 项准备生命周期检查，包含 14 条真实 Windows 函数表查找、注销、错误 metadata 拒绝、封存失败与清理失败重试。测试未发布任何 hook。
- 4,248 个 Windows 回溯现场，覆盖非易失通用寄存器、返回地址、栈以及 XMM6。三个独立反例分别保留旧拒绝顺序、使用旧帧大小、使用旧 XMM6 偏移，均产生预期失败。

功能执行使用 Unicorn。Windows 回溯测试把保存指令放在不可执行页上，只调用 `RtlVirtualUnwind`；准备测试只分配、封存、注册、查询和清理，不原生执行游戏函数。历史完整 bundle 的 golden 比对仍独立使用旧 builder，没有改写历史预期来适应本次结果。部分辅助函数使用保存的原指令，其余回调使用明确契约的替身。

## 接手顺序与尚未完成的部分

1. 已完成 `ep_roster_gate/group/call` 接入：2,760-byte 开关映像、15 条函数表记录、内部 getter 绑定第 3 个主体。整组 90 个分支、161 组非法配置、49,846 个 Windows 回溯现场通过；发布 SDK 前后失败涵盖所有十五处。受管调用含离队尾调用期间关闭/提交等待及嵌套删除异常，详见 [共同入口](ROSTER_GROUP.zh-CN.md) 与 [调用契约](ROSTER_CALLS.zh-CN.md)。
2. 审核离队前清理到实际删除之间的整个所有权范围、间接尾调用、回调重入、caller/helper ABI 与锁顺序。入口级 owner 只持续到本次调用返回，不自动延续到随后真实删除；这段资源生命周期仍未受完整保护。`605F28 JMP [R8+0x480]` 的目标 ABI 单独列为未验证。
3. 接通并验证真实人数通知资源。保存候选依赖另行准备的人数策略；`94C9C0` 的零人数仍钳为一，`60C2A0` 的第 5～8 人命名资源未证实。不能把本函数通知通过当作实际界面/资源已支持八人。
4. 补齐其他读写者、生产排空/失败策略、权威身份及全容量事务，再推进角色创建、控制、复制、战斗、死亡增援、离开重连与八账号完整任务。

早期回调可能已经改变外部资源，后续 getter 或其他路径拒绝不撤销此前副作用。`installable`、`runtime_verified`、`multiplayer_verified`、生产发布与自动绑定均仍为 false。旧 PID 的一次性 64 KiB 授权已用完，不延续到新的游戏访问。

总交接中的两个离线重建命令已纳入此模块。单独重放验证时，先完成引擎离线构建，再运行：

```powershell
$env:ZIG_GLOBAL_CACHE_DIR=Join-Path (Get-Location) 'work/hellforge-zig-cache'
$env:ZIG_LOCAL_CACHE_DIR=Join-Path (Get-Location) 'work/hellforge-zig-local-cache'
py -3.12 -B hellforge_multiplayer/tools/validate_departure_images.py `
  --library hellforge_multiplayer/build/property_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```
