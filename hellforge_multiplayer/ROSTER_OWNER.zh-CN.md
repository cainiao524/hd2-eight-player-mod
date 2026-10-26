# 八槽名册的存储所有者

2026-10-26，固定 HellForge SDK 13、游戏 build 25480438。`ep_roster_owner.*` 提供实际编译进研究 Mod 的并发、身份版本和关闭生命周期模块。当前已连接实际 loader 的离线消费者，十五入口可通过新增的 [受管调用接口](ROSTER_CALLS.zh-CN.md) 进入同一作用域。**生产 hook、所有游戏写入者和真实身份来源尚未绑定**。研究 Mod 初始化不调用它。

## 解决的问题与边界

原有 `EpNativeRosterSource` 只规定 begin/read/end 租约，没有实现谁持有锁、写入如何遵守、关闭如何等待。这次所有者在整个解码期间持有独占 SRW 锁，并在同一锁内执行 `mutate` 回调、发布身份票据与增加 revision。引用计数同时包含已经开始和排队等待的操作；关闭先拒绝新操作，再等待全部引用归零。

它只保护遵守该入口的操作。旧 `prepare` 接口继续使用直接转发开关；新 `prepare_owned` 把十五入口的旧/新完整调用置于 owner 内，并在取得保护后选择路径。内部搬移继承外层保护；同 owner 原生嵌套由 `ep_roster_owner_call` 支持。角色、descriptor、哈希表和本地身份等对象的其他写入者仍须覆盖；仅绑定读取器不能证明互斥完整。实际调用端、外部尾跳及运行期异常表的核对也仍是生产门槛。

本模块不分配 S/B、不会扩大游戏容量、不产生或认证玩家身份、不读取安装目录或游戏程序。底层内存复制始终来自调用方显式提供的 `EpRosterMemory.read`。离线测试的该回调只复制自有数组。

## 接口和使用顺序

1. 准备 `EpNativeRosterView`：明确 game、S、B、固定 build、非零 epoch，初始身份票据及 `lease=NULL`；准备底层复制回调和稳定 context。`create` 只检查数值与票据，不读取内存。不允许两个所有者绑定同一 game，或 S/B 完整范围相交，包括另一个 Mod 的所有者以及正在关闭的所有者。
2. `ep_roster_owner_create` 返回进程内单调递增的 handle。最多同时 8 个所有者。注册表槽位可以在关闭后重用，但 handle 不重用；计数溢出时拒绝，不能回绕。
3. `info` 提供当前 revision、epoch、票据数量与永久故障原因。首次 revision 为 1。`snapshot` 通过本所有者调用原有完整 B 布局解码器，持锁直到最后一次绑定复核完成。
4. `provider` 产生可交给私有 `EpHfRosterApi.bind` 的八容量 provider。context 是数值 handle，不是可重用槽位的地址。旧 provider 在关闭后只能返回不可用，不会读到后来占用同一槽位的会话。
5. 写入时调用 `mutate(mod, handle, expected_revision, next_tickets, callback, context)`。必须使用已观察到的 revision；旧 revision 或非法票据在执行回调**以前**拒绝。`next_tickets=NULL` 保留身份。回调在锁内修改自己拥有的原生数据，返回 1 才提交下一份票据并增加 revision；回调得到的是只读的旧绑定/身份视图。
6. 关闭前由生产集成停止原生新调用并排空相关 hook，完成正确的数据清理/回滚安排。`close` 拒绝新 owner 操作、等待读写与已排队操作，之后允许释放底层 context 和内存。排队但未开始的写入在看到关闭后取消。关闭不卸载 hook、不释放游戏资源、不把八槽数据恢复为四槽。
7. 卸载本模块的可执行代码前必须完成 loader provider 的解绑与排空。关闭后的 provider 虽然会拒绝读取，函数地址仍属于此 DLL。此模块没有伪装成可卸载的游戏 hook 生命周期。

调用方提供的参数和回调必须有效；回调采用 C ABI，不得抛出 C++ 异常或用 longjmp 离开。Windows 故障隔离不接管 C++ 异常对象的寿命。不得等待另一个 owner 操作或反向调用持有 loader 读取锁的接口。snapshot/mutate/close 等管理接口仍拒绝重入；snapshot 返回不可用，其余入口返回 `EP_OWNER_REENTRANT`。唯一开放的嵌套是原生 `call` 作用域中的同 owner 原生 `call`，最多 32 层，共享锁与最外层 revision 提交；跨 owner/Mod 和从普通 snapshot/mutate 发起的原生嵌套均拒绝。详细 ABI、错误返回与控制操作拒绝规则见 [受管调用说明](ROSTER_CALLS.zh-CN.md)。

## 身份、失败与异常

票据验证保留 peer、player entity、network index、generation、epoch 的独立含义。相同网络槽中仍然是同一个 peer/entity 时 generation 必须保持；新绑定或离队后重用该槽时，generation 必须严格大于该槽的历史最大值。删除不清除历史代次，`UINT32_MAX` 后该槽不允许继续复用，需要新的合法会话生命周期。数据数组重排不改变网络槽，也不会自动增代次。

这些规则能拒绝本地过期更新和槽位重用错误，**不能证明票据来自权威服务器**。网络接纳、权威索引分配、epoch 来源与认证仍须接入；不允许用这份本地账本自行推断真实玩家加入。

回调返回非 1 或发生 Windows 结构化异常时，可能已经部分写入：所有者保留故障状态，revision 和票据不提交，后续读写均拒绝。没有自动重试、清除故障或宣称数据已恢复。**隔离故障不是回滚**；部分写入的恢复和激活后的会话处置仍待生产事务完成。普通底层读取返回失败则只拒绝此次快照，允许后续重试；异常导致的读取失败会隔离该所有者。

异常边界使用单个静态汇编调用帧及 Windows `__C_specific_handler`，有正常 PE 回溯表。56-byte 栈帧保持对齐，故障指针放在被调用者 shadow space 之外；返回 PC 后保留一个 NOP，使它仍落在 handler 范围内。系统先回溯回调，再进入故障出口，释放 owner 锁及引用。未安装全局异常钩子，也不需要改变 HellForge `ModKit.Flags` 或增加 `-fms-extensions`。测试实际触发跨 DLL 的结构化异常，再验证快照拒绝、解绑和关闭完成。

原读取器每次快照仍最多请求 4,096 bytes；这不是新的游戏读取授权，历史一次性 64 KiB 采样预算仍为零。

## 已执行的验证

`tests/roster_owner_dll.cpp` 编译真实 `ep_roster_owner.cpp` 与读取器，未替换锁、读写算法或异常边界。`roster_owner_test.c` 使用真实补丁后的 loader 消费者，以及已有候选在 Unicorn 中生成的八人、移除后七人、重新插入八人三份存储夹具。Windows 测试不执行游戏函数体；写回调仅切换这些自有内存夹具。

测试覆盖：非法绑定/身份、跨 Mod 重叠所有者、普通读取失败可重试、重入拒绝、写入前 revision/票据校验、八→七→八生命周期及一次重新生成事件、槽位代次墓碑/耗尽、旧 provider 不串到新 owner，以及 8 个槽位的耗尽和重用。

并发测试直接观察生产注册表中的排队引用数量，再释放事件以确定执行顺序：写入暂停在只更新了 header 的位置，快照必须等待；快照暂停时写入不能开始；两个使用同一 revision 的写入只能成功一个；关闭等待实际 loader 读取和排队写入，后者取消。观察接口只读取队列状态，不修改实现或提供替代锁。

本轮 641 次检查通过。结果与源码、DLL/EXE、三个夹具的指纹记录在 `evidence/engine-roster-validation.json` 的 `roster_owner` 和共同指纹表中。使用 [引擎完整重建入口](engine/README.zh-CN.md#重建与证据) 自动重现；`build_offline.py` 同时将新模块按上游原有编译选项编入研究 DLL 与源码 ZIP。

## 下一步

十五入口受管桥接已提供显式集成接口；继续核对其余写入者、外部辅助函数 ABI 与调用锁顺序，落实生产排空、真实拒绝契约、权威票据、底层内存寿命和完整容量事务。继续解决分类临时分配失败、caller flag/通知、角色创建/控制、复制、增援、任务结算及八个独立账号验收。`installable`、`runtime_verified`、`multiplayer_verified` 均保持 false。
