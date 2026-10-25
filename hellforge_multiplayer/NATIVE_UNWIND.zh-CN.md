# 原生属性发送候选：Windows x64 栈回溯

2026-10-25。固定游戏 build 25480438，发送函数原入口 `0x60C640`。本次提供代码生成器、`UNWIND_INFO` 与 `RUNTIME_FUNCTION`，并在自有测试进程内验证 Windows 回溯。**尚未安装游戏 hook，也未完成可用的八人 Mod。**

## 实际改动

`tools/native_producer_unwind.py` 复用固定指纹的旧发送候选，保持八槽属性地址、参数、最终栈布局、返回值和拒绝原因，增加两项变更：

- 将 24-byte prologue 改为先保存 RDI/R14/R15 并分配栈，再在同一最终地址保存 RBX/RBP/RSI。长度、后续指令位置和最终栈内容相同；这样各个未完成的 prologue 阶段也能由同一份回溯资料描述。
- 两个拒绝出口原为 `MOV R10D,reason; JMP external`。由于此时仍持有内部栈帧，外部直接跳转会被 Windows 当作尾调用式 epilogue。新代码使用 `TEST R10D,R10D; JNZ external`，保持非零 reason、所有 GPR 和栈内容；只改变原拒绝 ABI 未承诺保留的标志位。内部跳转重新定位，不截断 rel32。

代码 670 bytes；24-byte unwind 资料位于偏移 672；12-byte 函数表位于偏移 696；完整映像 708 bytes。函数范围覆盖原 body 和附加 guard，结束于偏移 670，不包含元数据或外部拒绝处理。整个映像会检查与已知引用区域的重叠，仍须由集成者提供真实、独占且生命期足够的分配。

Windows 对动态代码函数表和回溯信息的要求见 [x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170)；测试调用 [RtlVirtualUnwind](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtlvirtualunwind)。

## 实际验证

1. Unicorn 执行 12 个发送场景：八个 ordinal、越界 ordinal、missing sentinel、错误绑定和缺失本地 confirmed-peer 索引。复用原独立 oracle，核对全部非栈页面、八个属性描述符、计数、分配器调用、寄存器和拒绝时无数据写入。
2. 从上述执行采集 1,308 个候选指令位置的寄存器和栈内容，包括部分 prologue、body、guard、正常 epilogue 与拒绝分支。
3. 自有 C 测试进程将代码放在 **PAGE_READWRITE、不可执行** 内存中，注册函数表，逐个用 Windows `RtlVirtualUnwind` 恢复调用者。全部位置恢复正确返回地址、RSP 和八个非易失 GPR。候选代码只在模拟器中执行，没有在宿主上原生执行。
4. 对照组使用相同的规范化 prologue 和 unwind 资料，但保留旧的 E9 拒绝跳转。1,302 个普通位置通过，3 次拒绝跳转的回溯错误按预期复现。这里没有把对照组说成原始候选逐字节不变。
5. 两份函数表均注册、查找、撤销成功；撤销后再次查找无残留。另检查新增指令使 rel32 越界、完整代码/元数据与拒绝地址重叠、代码指纹改变这三种拒绝情况。
6. 八端属性转发链路已改用这份发送候选，再验证实际后端转发、56 次原生接收和八份名册消费者。接收函数仍使用原候选，其 Windows unwind **尚未实现**。

收据：`evidence/native-producer-unwind-validation.json`，包含源码和产物 SHA-256。总引擎收据同时固定该收据的指纹。1,308 是逐指令上下文数量，不是玩家数、游戏测试次数或独立场景数。

## 离线重建

```powershell
py -3.12 -B hellforge_multiplayer/tools/build_unwind_offline.py `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

完整的 `tools/build_engine_offline.py` 已自动包含此验证。依赖仍是固定 Zig、Unicorn 2.1.4 和 Capstone 5.0.7。

`build/producer-unwind-image.bin` 绑定测试的合成地址，不能直接装进游戏。若后续集成者已取得并验证真实分配，可通过生成器的 `--game-base`、`--code-address`、`--roster-address`、`--property-address`、`--reject-address` 和 `--output` 生成对应 JSON；输出必须是新文件。这个入口只生成数据，不分配执行内存、不读取地址、不注册函数表、不安装 hook。

## 尚未完成的接入

外部拒绝处理仍必须接受已有内部栈帧，终止整个属性阶段并拥有自己的正确回溯资料；不能换成普通 RET。生产环境还需先注册函数表，再发布入口，撤销入口并等待所有执行者退出后才撤销表和释放内存。本次只验证正常栈回溯，没有实现异常资源清理、生产函数表所有者或 hook 安装事务。生成资料没有语言级异常处理器；原函数的 handler flags/扩展异常资料尚需核对，不能把回溯通过解释为完整异常处理等价。

接收函数 `0x60C890` 有条件保存/恢复 RBX、RSI、RDI 的分支，不能直接套用发送函数的数据。其他原生候选、真实玩家容器与并发写入排除、身份票据、角色创建/复制及完整任务验证仍分别待完成。网络字段类型资料不足，本轮没有依据猜测修改玩家索引的编码宽度。没有新增游戏访问授权。
