# HellForge 会话内原生代码所有权

适用固定上游 `a4dd089eb56cdd5cd96c3cefe6e80eba5848d6fa`，SDK 13、build 25480438。实现为 `mod/src/ep_session_code.*`；研究 Mod 初始化不会调用它。

## 实际接入点与生命期

上游 `native/mod-loader/hooks.c` 的 `ApiHookEx` 会保留传入的 `original` 变量地址。以后有新 hook 插入同一链时，它会重写该变量；复制一次指针或使用栈上临时变量都不满足这个契约。上游 hook 保留整个会话，也没有 SDK 移除入口。

本实现以固定槽位保存下一跳变量，通过真正的 SDK `hook_ex` 接入链；没有另写独立入口补丁。每个模块最多 64 槽，每个代码映像最多 65,536 bytes，句柄单调递增，取消后旧句柄不能操作新对象。此上限是本进程代码分配上限，与旧 64 KiB 游戏唯读采样预算无关。

生命周期如下，所有接口成功返回 1，和 SDK hook_ex 成功返回 0 的约定不同：

1. `reserve`：验证 API 长度、版本和 build；只在当前进程分配不可执行的 RW 内存，返回基址及固定下一跳变量的地址。指定基址时必须精确分配；没有自动扫描游戏或寻找可用地址。
2. 由调用方在这个基址生成、重定位并校验代码。现有 [进程内属性生成器](PROPERTY_IMAGES.zh-CN.md) 已实现发送/接收两份候选，并通过 `ep_property_code_prepare` 接到本模块；它不由 Mod 初始化自动调用。Python 生成器保留为独立离线参考。
3. `seal`：复制映像到独占内存，验证一个从偏移 0 开始的 RUNTIME_FUNCTION；新增 `seal_table` 接受一条或两条，检查排序、范围和独立回溯区间。只支持无 handler、无 frame register 的版本 1 资料以及当前候选使用的 PUSH_NONVOL、ALLOC_SMALL 和 SAVE_NONVOL；封为 RX、刷新指令缓存，再按实际条数注册函数表。失败后不能发布。
4. `publish`：先将所有者模块固定到进程结束，再将映像标为不可取消，之后调用 SDK。固定槽位及其下一跳变量始终存在；后续链更新可以改写下一跳。禁止把本所有者的任何映像（含页尾空白）当作另一个 hook 的目标。
5. `discard`：仅允许从未尝试发布的映像。先撤销函数表，再释放内存。撤销失败保留原表和内存，释放失败也保留记录供重试。

`seal` 验证回溯资料的结构，不解码并证明任意代码与回溯资料等价。集成者仍必须使用已验证的生成器、核对目标函数和运行期异常表，并保证所有外部引用的地址与资源生命期。

Win32 要求动态代码提供函数表，注册成功才算存在，见 [RtlAddFunctionTable](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtladdfunctiontable)。可执行页修改后的缓存要求见 [VirtualProtect](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualprotect)。模块固定使用 FROM_ADDRESS 与 PIN，后者持续到进程结束，见 [GetModuleHandleExA](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getmodulehandleexa)。

## 发布失败的处理

SDK 报错并不足以证明代码从未暴露。任何一次 `hook_ex` 调用开始后，不论成功、失败或仍在进行，都会保留代码、函数表和下一跳变量，禁止重试发布或释放。失败需要向上层报告，不能继续宣称容量事务成功。

这是与上游会话 hook 相容的内存生命期策略，**不是完整的扩容回滚或热卸载**。[属性成组入口](PROPERTY_GROUP.zh-CN.md) 已用默认关闭的转发入口避免部分发布就启用属性候选；真实暂停/排空、所有容量的数据事务和激活后回滚仍待实现。关闭会话、重新启动应用后的移除步骤也须在可安装版本中说明。

## 离线验证方法

`tests/session_code_test.c` 直接包含补丁后的实际 HellForge loader，通过真实 `ApiHookEx`、`HookAdd` 与 MinHook 修改测试程序自己分配的小函数。没有启动 loader 的 Watch、识别游戏程序或读取已安装游戏。MinHook 内部使用系统线程快照，只把当前测试 PID 的线程加入暂停/恢复列表；没有打开其他进程，也没有操作其他进程的线程。

测试包含：

- 两份实际属性候选映像的注册、查找、取消；只注册数据，绝不在宿主上调用这些游戏候选。
- 错误 owner、过期句柄、API/build/范围错误、八种异常资料错误；保护页、缓存刷新和注册失败时禁止发布。
- 函数表撤销或内存释放失败时保留记录，再重试完成。
- 发布阻塞期间并发取消和重复发布被拒绝，函数表保持有效。
- 五个真正进入 HellForge 共用链的合成函数；优先级排序、后插入 hook 改写旧下一跳变量、调用返回值都核对。合成函数只执行测试专用运算和转发，不执行游戏函数体。
- SDK 在发布前报错，以及故意在真实发布后报错；两个失败映像都保留，后者仍能经链调用。
- 64 槽耗尽时拒绝新分配，不替换已发布对象。
- 单独构建的测试 DLL 发布后调用 FreeLibrary，核对模块仍存在，下一跳变量与函数表有效，整条链仍可调用。

完整 `tools/build_engine_offline.py` 自动构建测试与 `session_code_owner_test.dll`，383 次检查通过，结果写入 `evidence/engine-roster-validation.json` 的 `session_code_owner`，同时固定源码和产物指纹。测试结束前刻意不伪造上游不支持的 hook 移除；已发布的测试资源留到该测试进程退出。`build_offline.py` 也已完成正式 C++ 编译、26 项适配器与 132 项后端基线检查，并核对源码 ZIP 内的新模块。

生产接入仍缺：运行期版本/代码/异常表核对、其他候选的进程内生成与回溯资料、外部拒绝处理、共同激活 guard 和完整资源事务、真实名册写入排除与资源所有者，以及角色建立、复制和完整八人任务实测。成组模块的 355 次检查另记，不并入这里的 383 次所有者检查。
