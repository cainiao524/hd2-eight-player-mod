# 实体 ID 到网络索引的原生查询

2026-10-25。固定游戏构建 25480438、HellForge SDK 13。`mod/src/ep_getter_image.*` 已把入口 RVA `0x606AD0` 的八槽查询候选加入 Mod 内部生成、重定位和封存流程。它与属性发送调用的 `0x134F190` 是两个不同函数，不能互换。

这条查询以前读取原位四槽属性表，现改为读取统一 B 存储内的属性记录。它是完成存储迁移所需的一个读取入口；独立准备接口仍只到 READY；它现已加入发送/接收的三入口共同开关，可由组统一发布和启用。Mod 初始化尚未调用，也没有游戏内发布。

## 接口与保持的行为

`EpGetterAddresses` 明确接收游戏基址、候选代码地址、名册地址、**整个 B 存储地址**和拒绝出口。属性发送/接收接口接收的则是属性区地址，二者不要混用。查询输入仍为 EDX 的实体 ID；按原管理器哈希表找到 ordinal，再读取 `B + 0x580 + ordinal*32 + 0x0C` 的完整 DWORD 网络索引。

- ordinal 是记录位置，网络索引是属性值；删除压实可改变前者，不应改变后者。
- 查询保留完整 DWORD，包括高位值和 `0xFFFFFFFF`，不把它强制夹到 0～7。
- 缺失项、sentinel 和空表保持原来的返回行为；五种结构拒绝原因保留。待完成记录可按 T 范围查询，不强制 T=D。
- 哈希容量不被硬编码为 8；既有测试覆盖 1、2、4、8、16 的碰撞与查找。它不代替完整名册快照校验，外部哈希存储有效性和读写排除仍由生产所有者负责。
- 函数保持原参数、非易失寄存器及返回栈约定，仅使用栈上的保存槽，不修改 B 存储。

`ep_getter_image_build` 只检查数值并产生字节，不读取传入的地址。它验证低 canonical 范围、对齐、已知区间重叠和 signed rel32；失败清零输出。重叠范围包括代码后的全部回溯资料。该检查不证明当前游戏地址可读、映像相符或对象仍存活。

| 内容 | 大小/位置 |
|---|---|
| 候选代码 | 354 bytes |
| UNWIND_INFO | 偏移 356，20 bytes |
| RUNTIME_FUNCTION | 偏移 376，12 bytes |
| 完整映像 | 388 bytes |
| 重定位 | 5 处：两处游戏全局、名册、B 存储偏置、拒绝出口 |

`ep_getter_code_prepare` 使用同一个会话代码所有者：先分配 RW，按实际基址生成，再封为 RX、刷新指令缓存并登记函数表，成功返回 READY。生成或封存失败时释放；释放失败则返回 `EP_PROPERTY_CLEANUP` 并保留可重试句柄。它没有 SDK 发布动作。返回码与属性生成接口相同，成功为 0；所有者接口本身成功为 1。

## 原始回溯来源

`native-getter.lock.json` 固定原始 165 bytes 代码、旧生成器证据、测试文件及已有捕获的指纹。离线重放逐字节核对保存的函数表记录 RVA `0x380A7F0` 和 UNWIND_INFO RVA `0x2424C2C`，合计 32 bytes 元数据；没有新增游戏读取。

原始回溯信息为 version 1、prologue 20 bytes、四个 SAVE_NONVOL，无 handler、无 chain、无 frame register。候选保持这段入口与栈布局，拒绝出口前已恢复寄存器，因此无需照搬发送/接收函数的 prologue 或拒绝跳转改写。函数表的结束地址更新到完整候选末尾。格式依据 [Microsoft x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170)。

模板由 `tools/generate_getter_template.py` 从固定来源生成。默认仅核对；显式 `--write` 才更新头文件。C++ 不接受外部任意模板，运行时也不依赖 Python。与属性来源相同，保存 PE 头指向的异常目录未完整捕获，**运行期有效异常表仍未确认**。

## 已执行的验证

收据：`evidence/native-getter-validation.json`，并由总引擎收据交叉固定指纹。

| 范围 | 结果 |
|---|---|
| C++ 与独立 Python 的完整映像比对 | 13 组通过，49 组错误地址/范围输入拒绝 |
| API 与来源保护 | 2 项 API、2 项来源拒绝检查通过 |
| 原有功能测试 | 7 个测试通过；71 次候选查询、11 次原始对照查询、1 次分类和 1 次删除，共 84 次执行记录 |
| Windows 回溯 | 4,548 个执行位置的上下文通过；另有 1 次人为破坏 RBX 保存偏移的负面对照被拒绝 |
| 实际分配/封存/清理 | 25 项生命周期检查通过，含函数表查找、保护失败及释放失败后重试 |
| 八端属性转发后的查询 | 64 次通过，每端查询全部八名成员 |

功能测试使用 C++ 实际生成的代码在 Unicorn 内执行，包括删除压实后的再次查找；分类用的外部 helper 仍是固定测试桩。4,548 个上下文交给自有进程中的真实 Windows 回溯 API，**没有在 Windows 宿主直接执行游戏候选函数体**。人为破坏的负面对照不代表原始 getter 存在已发现的回溯错误。

八端测试先完成 56 次实际 HellForge 后端转发和接收，再以每端自己的实体 ID 经实际生成的共同入口查询八人。网络索引为 `(3*peer+2)%8`，与各端 ordinal 排列分开；逐次核对返回值、参数、栈、非易失寄存器及没有栈外写入。64 条查询记录保存在被忽略的 `build/native-sync-received.json`，其指纹由总引擎收据固定。

完整重建沿用 [引擎离线构建入口](engine/README.zh-CN.md#重建与证据)，会自动构建测试 DLL、运行 getter 验证和八端查询。仅重跑 getter 时使用：

```powershell
py -3.12 -B hellforge_multiplayer/tools/validate_getter_image.py `
  --library hellforge_multiplayer/build/property_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe
```

## 尚未完成的生产连接

现有成组入口覆盖属性发送、接收和本 getter；其余读写入口仍需纳入统一发布/启用方案。生产拒绝处理、运行期来源/ABI/异常表核对、排空已选旧路由的调用、覆盖全部写入者的互斥租约、完整容量事务与激活后数据回滚仍未实现。单独增加本查询或一把锁不能满足这些条件。

真实身份票据、角色创建/控制/复制、游戏封包和实体分派、计分/customization 四槽边界，以及完整八人任务仍待完成。`installable=false`、`runtime_verified=false`、`multiplayer_verified=false`。当前工作没有安装、启动、检查或读取游戏；PID 30776 的旧一次采样额度已经消费。
