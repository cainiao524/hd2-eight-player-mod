# 八格玩家状态更新与原栈保护处理器

固定游戏 build 25480438、HellForge SDK 13。`6054F0` 已移植为 C++ 映像，并作为共同发布组第 17 个入口。历史文件名 `arrival` 仅沿用研究命名：函数会查名册、更新状态与关联对象、选择显示颜色并发送人数通知，没有增加人数或建立角色的代码。此交付不是第五名角色生成或八人任务完成证明。

## 来源与行为

`native-arrival.lock.json` 固定保存的完整 1,111-byte 原函数、原异常表记录、两段栈保护处理器代码以及旧候选/夹具来源。重建只读取仓库内 `evidence/existing-code-evidence-25480438`，不访问安装目录或游戏进程。保存异常表和 PE 头所指目录不同的原有限制继续保留，不能把保存表当作已核对的运行期表。

19 个数组访问点连接共同 B：pointer 2 个、primary 4 个、aux 9 个、property 4 个。原 S 继续用于 map/header/count。入口保留十类检查，包括 S 身份、参数非空、`P≤D≤T≤8`、八格 map、ID、ordinal 和目标指针一致。拒绝出口先设置 R10D，再恢复寄存器和栈，使每条恢复指令都符合 Windows 尾声识别规则。

索引和 ordinal 仍分开处理。network index 小于 4 时读取原四行 palette；4～7 保留原 `(255,255,255)` 回退，没有扩大四行表或伪造新显示资源。三个通知使用原当前 dense count；没有套用离队的预测减一规则。两个在成功 guard 下不可达的原 invalid-ordinal 分支仅有静态检查，其余 17 个数组访问点有功能轨迹检查。

## 为什么需要单独保留 GS 处理器

原 `UNWIND_INFO` 首 byte 为 `0x19`，含 `EHANDLER|UHANDLER`。后面是 RVA `0x21044A0` 与 handler data `0x60`。保存的处理器读取 DispatcherContext 的 HandlerData，转交 `0x21044C0`；后者从 frame+96 取 cookie、按 frame 解码后尾跳 `0x2088770`。不能把首 byte 改为 `0x01` 来满足旧封存接口。

新独立映像保留原 128-byte 固定帧、R14 push、四个 home-slot 保存和 XMM6 保存。原 handler flags 与 cookie offset 保留，用本映像内的五字节相对跳转转交显式绑定的原处理器。没有复制或替换实际 security-check helper，没有通用 SEH scope-table 翻译或任意语言 handler 支持。

| 项目 | 独立映像 | 共同组第 17 项 |
|---|---:|---:|
| 完整 bytes | 2,024 | 2,072 |
| 代码末端 | 1,925 | 1,957 |
| 函数表记录 | 3 | 4 |
| GS handler 跳转 offset | 1,920 | 1,952 |
| 带 GS 的函数表 index（从 0 开始） | 1 | 2 |
| cookie 相对固定 frame offset | 96 | 96 |

`ep_session_code_seal_gs_table` 必须显式提供处理器目标及表中位置。它校验固定原 metadata 格式、EH/UH flags、cookie offset、owned thunk 的独立 leaf 记录和实际 rel32 目的地。原 `seal_table` 继续拒绝 handler。结构校验不替代原指令、实际目标身份与内存生命期的核对。

成组生成时同时将函数表、链式父记录和 GS handler RVA 加 32。第 17 项与其他入口共用 B、owner 和激活开关；旧/新调用都可通过受管桥，状态更新按写操作处理。代码槽增至 68，以容纳四组各 17 项；每幅映像仍最多 65,536 bytes。这里的代码分配上限与旧只读采样的 64 KiB 预算是两件事。

## 验证与重建

完整重建入口见 [引擎说明](engine/README.zh-CN.md)。它编译 `tests/arrival_image_dll.cpp`，再运行 `tools/validate_arrival_images.py`，并将结果接入 `evidence/engine-roster-validation.json`。独立收据为 `evidence/native-arrival-validation.json`，共同开关收据为 `evidence/roster-gate-validation.json`。

独立验证包含 5 个功能方法、42 次执行：4 次原四格基线、21 次候选正常返回、17 次入口拒绝。当前 C++ 输出与 Python 地址重定位参考完整比对，18 组合法位置、64 组拒绝位置、2 项 API 契约及 59 项实际准备/回收检查通过。

Windows 对 3,899 个合成功能现场分别执行 NHANDLER、EHANDLER、UHANDLER 回溯，核对八个非易失 GPR、XMM6、RSP、返回位置、处理器地址、HandlerData 和 frame。三份负对照分别破坏拒绝尾声、帧大小和 XMM6 保存位置，均能检出。上下文数不是游戏运行次数。

另在 Unicorn 执行实际生成的 thunk 和保存的两段 GS 指令：两个基址各有正常 cookie 与单 bit 损坏 cookie，共四例。实际检查 helper 作为明确替身，只核对传入 cookie；损坏例在该边界停止，不宣称执行了游戏 fail-fast。Windows 只处理生成代码的 metadata，不原生执行游戏指令。

十五类不合法 GS 封存输入包括移除 handler、丢失 UH flag、错误 cookie/alignment、错误 thunk/RVA/目标、错误 frame metadata 与越界描述符，均拒绝。共同组测试覆盖每个入口发布前后故障、准备失败清理、原链保留和 owner 排空；原状态更新主体与宿主合成回调分别验证，尚未在真实游戏中联合执行。

## 仍须完成

初始化没有自动绑定或发布这一组。还需权威身份和内存生命期、全部 reader/writer、真实重入及锁顺序、生产排空、完整容量事务和失败回滚。处理器目标与 cookie 全局的运行期身份仍需合法运行期核验。

第 5～8 名的真实角色资源、创建入口、控制、复制、死亡/增援及八独立账号完整任务仍未完成。原删除回调返回数量契约、`605F28` 间接尾目标和剩余实体分支仍待解决。维持 `installable=false`、`runtime_verified=false`、`multiplayer_verified=false`；旧一次性采样授权不续用。
