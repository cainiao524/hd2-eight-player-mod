# 原生属性发送与接收候选：Windows x64 栈回溯

2026-10-25。固定游戏 build 25480438，发送函数原入口 `0x60C640`，接收函数原入口 `0x60C890`。两份代码生成器分别提供 `UNWIND_INFO` 与 `RUNTIME_FUNCTION`，并在自有测试进程内验证 Windows 回溯。**尚未安装游戏 hook，也未完成可用的八人 Mod。**

## 发送候选

`tools/native_producer_unwind.py` 复用固定指纹的旧发送候选，保持八槽属性地址、参数、最终栈布局、返回值和拒绝原因，增加两项变更：

- 将 24-byte prologue 改为先保存 RDI/R14/R15 并分配栈，再在同一最终地址保存 RBX/RBP/RSI。长度、后续指令位置和最终栈内容相同；这样各个未完成的 prologue 阶段也能由同一份回溯资料描述。
- 两个拒绝出口原为 `MOV R10D,reason; JMP external`。由于此时仍持有内部栈帧，外部直接跳转会被 Windows 当作尾调用式 epilogue。新代码使用 `TEST R10D,R10D; JNZ external`，保持非零 reason、所有 GPR 和栈内容；只改变原拒绝 ABI 未承诺保留的标志位。内部跳转重新定位，不截断 rel32。

代码 670 bytes；24-byte unwind 资料位于偏移 672；12-byte 函数表位于偏移 696；完整映像 708 bytes。函数范围覆盖原 body 和附加 guard，结束于偏移 670，不包含元数据或外部拒绝处理。整个映像会检查与已知引用区域的重叠，仍须由集成者提供真实、独占且生命期足够的分配。

## 接收候选

`tools/native_receiver_unwind.py` 复用固定指纹的旧接收候选。原入口先保存 RBP、再压入 R14；RBX、RSI、RDI 只在实体查找的一部分路径保存，sentinel 分支会跳过它们。

新的 22-byte prologue 先压入 R14，再把 RBP/RBX/RSI/RDI 保存到原先最终使用的四个调用者预留槽位。原来的三处条件保存替换为同长度 NOP，原恢复指令保留。最终 RSP 仍是入口 RSP 减 8；正常返回、拒绝原因和非栈数据效果由原独立 oracle 核对。sentinel 路径比原先多写三个合法的栈槽位，因此不宣称整片栈逐字节不变。

接收端的两个拒绝跳转也改为上述 TEST/JNZ。入口加长后，全部直接分支、RIP 相对 sentinel 读取和 splice/恢复地址重新定位。接收代码 398 bytes；24-byte unwind 资料位于偏移 400；12-byte 函数表位于偏移 424；完整映像 436 bytes。使用接收端自己的回溯表，不能套用发送端的表。映像同样检查地址范围和已知区域重叠。

Windows 对动态代码函数表和回溯信息的要求见 [x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170)；测试调用 [RtlVirtualUnwind](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtlvirtualunwind)。

## 实际验证

1. Unicorn 执行 12 个发送场景：八个 ordinal、越界 ordinal、missing sentinel、错误绑定和缺失本地 confirmed-peer 索引。复用原独立 oracle，核对全部非栈页面、八个属性描述符、计数、分配器调用、寄存器和拒绝时无数据写入。
2. 从上述执行采集 1,308 个候选指令位置的寄存器和栈内容，包括部分 prologue、body、guard、正常 epilogue 与拒绝分支。
3. 自有 C 测试进程将代码放在 **PAGE_READWRITE、不可执行** 内存中，注册函数表，逐个用 Windows `RtlVirtualUnwind` 恢复调用者。全部位置恢复正确返回地址、RSP 和八个非易失 GPR。候选代码只在模拟器中执行，没有在宿主上原生执行。
4. 对照组使用相同的规范化 prologue 和 unwind 资料，但保留旧的 E9 拒绝跳转。1,302 个普通位置通过，3 次拒绝跳转的回溯错误按预期复现。这里没有把对照组说成原始候选逐字节不变。
5. 两份函数表均注册、查找、撤销成功；撤销后再次查找无残留。另检查新增指令使 rel32 越界、完整代码/元数据与拒绝地址重叠、代码指纹改变这三种拒绝情况。
6. 接收端按相同方法执行 17 个场景：八个 ordinal、ordinal 8 与 0xFFFFFFFF、错误绑定、实体 sentinel、零容量、空桶、满表未命中、碰撞后命中，以及完整 DWORD 网络索引传递。最后一个用例只验证字段没有被截断，不把这个大数解释为合法玩家槽位。原独立 oracle 核对全部非栈页面、属性值、payload 读取、游标、寄存器和拒绝效果。
7. 接收端的 1,313 个上下文覆盖 101 个不同指令位置，全部通过 Windows 回溯；其对照组 1,299 个普通位置通过、7 次旧拒绝跳转错误按预期复现。复用同一个 C 测试程序，代码同样不可执行，两份函数表均撤销无残留，三种地址/源码拒绝检查通过。接收端对照组也使用规范化入口，不能误记为未经改动的原候选。
8. 八端属性转发链路同时改用两份新候选，再验证 8 次发送、56 次实际后端转发和接收，以及八份名册到实际 loader 的 1,678 次断言。完整游戏封包和实体分派仍由测试桥接，详情见 [NATIVE_SYNC.zh-CN.md](NATIVE_SYNC.zh-CN.md)。

收据分别为 `evidence/native-producer-unwind-validation.json` 与 `evidence/native-receiver-unwind-validation.json`，包含源码和产物 SHA-256；总引擎收据同时固定两份收据指纹。1,308 与 1,313 都是逐指令上下文数量，不是玩家数、游戏测试次数或独立场景数。

## 离线重建

```powershell
py -3.12 -B hellforge_multiplayer/tools/build_unwind_offline.py `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe

py -3.12 -B hellforge_multiplayer/tools/build_receiver_unwind_offline.py `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

完整的 `tools/build_engine_offline.py` 已自动包含两组验证。依赖仍是固定 Zig、Unicorn 2.1.4 和 Capstone 5.0.7。

`build/producer-unwind-image.bin` 和 `build/receiver-unwind-image.bin` 绑定测试的合成地址，不能直接装进游戏。若后续集成者已取得并验证真实分配，可通过对应生成器的 `--game-base`、`--code-address`、`--roster-address`、`--property-address`、`--reject-address` 和 `--output` 生成 JSON；输出必须是新文件。两个入口都只生成数据，不分配执行内存、不读取地址、不注册函数表、不安装 hook。接收端命令行已另验证生成成功、重复输出被拒绝且原文件内容不变。

## 尚未完成的接入

外部拒绝处理仍必须接受已有内部栈帧，终止整个属性阶段并拥有自己的正确回溯资料；不能换成普通 RET。生产环境还需先注册函数表，再发布入口，撤销入口并等待所有执行者退出后才撤销表和释放内存。本次只验证正常栈回溯，没有实现异常资源清理、生产函数表所有者或 hook 安装事务。生成资料没有语言级异常处理器；原函数的 handler flags/扩展异常资料尚需核对，不能把回溯通过解释为完整异常处理等价。

其他原生候选、真实玩家容器与并发写入排除、身份票据、角色创建/复制及完整任务验证仍分别待完成。网络字段类型资料不足，本轮没有依据猜测修改玩家索引的编码宽度。没有新增游戏访问授权。
