# 元件 33：核心、分类、初始化与直接入口的八槽离线实现

更新：2026-10-26。C++ 已能生成十四个映像：原有核心、分类、属性与单项重置八项，另有三个直接插入/移除入口、两个批次重置入口及一个保留身份的待加入分区转换。它们的数组访问使用独立八槽区域。密集插入和移除现已增加保留 pending 记录的修复，允许通过一致性检查的混合分区。**这只是元件 33 的部分生命周期，剩余读写者、生产发布与角色创建仍未完成。** 没有启动、检查、读取、修改或安装游戏。

## 文件与固定来源

- [native-component33.lock.json](native-component33.lock.json)：保存代码和回溯元数据的固定指纹。
- [mod/src/ep_component33_image.h](mod/src/ep_component33_image.h)、[实现](mod/src/ep_component33_image.cpp)：纯数字地址到字节映像的生成接口。
- [tools/native_component33_image.py](tools/native_component33_image.py)：逐条检查保存指令、重定位数组访问、保留原始函数片段与回溯链。
- [tools/generate_component33_templates.py](tools/generate_component33_templates.py)：生成并检查 C++ 模板。
- [tools/validate_component33_images.py](tools/validate_component33_images.py)：执行 C++ 实际输出，比较原版行为、独立数据模型、拒绝路径和 Windows 回溯。
- [evidence/native-component33-validation.json](evidence/native-component33-validation.json)：功能用例、定位拒绝、源码和产物指纹。
- [tools/validate_component33_classify.py](tools/validate_component33_classify.py) 与[分类收据](evidence/native-component33-classify-validation.json)：执行保存的回调包装器和分类映像，检查数据交换、条件序言回溯以及分配失败反例。
- [tools/validate_component33_initialize.py](tools/validate_component33_initialize.py)、[初始化夹具](tools/component33_initialization_fixture.py)与[初始化收据](evidence/native-component33-initialize-validation.json)：执行第二/第三回调，检查属性描述符、部分记录重置、GS 栈保护和分类后的连续操作。
- [tools/validate_component33_direct.py](tools/validate_component33_direct.py) 与[直接入口收据](evidence/native-component33-direct-validation.json)：直接入口、批次重置、同 ID 生命周期和未迁移分区函数的原版反例。
- [tools/validate_component33_transition.py](tools/validate_component33_transition.py) 与[批次转换收据](evidence/native-component33-transition-validation.json)：原版无损状态等价、全分区身份保留、重复调用、连续操作和错误元数据对照。
- [CREATION_DISPATCH.zh-CN.md](CREATION_DISPATCH.zh-CN.md)：与保存的创建分派及八槽名册相连的验证。

来源仍是已保存的 build 25480438 capture 与 `component33_250_lifecycle_evidence_v2.json`。搬移 `665FE0`、普通插入 `51ABF0`、密集插入 `51AC70`、移除 `51AD30`，以及真实 map 插入 `172F790`、删除 `172F8A0` 的完整字节均与保存证据核对。此步骤没有重新读取游戏。

## 存储布局

`S = owner+3CA0` 保持原位置。原全局指针 `EXE+33267B8`、组件头、计数和八桶内联 map 的地址不变；原 owner/registry 别名因此仍指向同一个头部。四组数组改由调用方持有的 `B` 存储，长度 `0x490`（1,168 bytes），16-byte 对齐。

| 数据 | 新位置 | 每项大小 | 八项的半开区间 |
|---|---:|---:|---|
| 实体指针 | `B+000` | `8` | `[000,040)` |
| 字节状态 | `B+040` | `1` | `[040,048)` |
| primary | `B+050` | `50` | `[050,2D0)` |
| secondary | `B+2D0` | `38` | `[2D0,490)` |

表中数字均为十六进制。`[048,050)` 是对齐空隙。旧 `S+70..S+2B8` 数组区域作为哨兵检查，候选十四函数不再写入它。

每条原数组指令前后用不改变标志位的地址装载切换基址，原指令本身保留。指针、primary、secondary 的地址偏置分别是 `B-70`、`B-48`、`B+F8`。非数组字段仍访问 `S`，调用的真实 map 函数也使用原 map 头。

原搬移器只复制指针、primary、secondary，**不复制字节状态、不清空来源槽位**。当前实现保留这些差异。插入只清零原代码清零的 primary；secondary 和字节状态由后续生命周期负责，不能从插入返回推断它们已初始化。

## 分类进入与退出

保存的 `51AEA0` / `51AEB0` 回调各为八字节：先把实体指针从 RCX 送入 RDX，再尾跳到 `666A90` / `666DD0`。新增映像保留 helper 的 RDX 实体参数；验证既执行重定向后的真实包装器，也直接调用 helper。回调登记、完整主体和原六段回溯数据均已固定在来源锁中。

进入把目标项与 `P` 边界项交换，最后 `P++`；退出把目标项与 `P-1` 交换，最后 `P--`。两者均交换指针、primary、secondary 并更新两条 map 序号。进入不搬动 byte；退出只做 `byte[target] = byte[P-1]`，边界 byte 保留。目标已处于边界时只改变 P，不分配临时缓冲。T、D、高水位和实体 flag 保持不变；flag 与通知仍由调用方管理。

进入/退出分别重定位 35/37 处数组访问，生成 2,264/2,384-byte 映像，各有四条函数表记录。byte 使用 `B-50` 地址偏置。进入仅接受 `[P,D)` 内目标，退出仅接受 `[0,P)` 内目标；预检同时核对目标和边界项的身份、map 序号、空槽计数以及保存的 invalid-ID 全局。错误分区、空指针、重复身份或不一致序号在写入前拒绝。

这两个原函数仅在需要交换时保存 R12、R15。条件序言中插入数组基址切换后，R15 保存结束偏移由 23 变为 43，因此同时重定位 PrologSize、每个 unwind CodeOffset 和片段链；原保存位置与操作保持不变。负对照重新装回旧的 23-byte 序言偏移，确认 Windows 会在尚未执行保存指令的中间位置恢复错误的 R15，修正记录通过同一上下文。

临时对象的初始化、分配、两次清理使用明确的契约替身，测试会改写所有易失整数寄存器、XMM0–5 和 shadow space；实际游戏分配器尚未执行。四个空分配对照（原版/候选、进入/退出）均复现：指针已交换，第一次临时分配返回零后发生无效内存访问，尚未更新分类计数，也未清理。因此 **分配失败回滚仍未实现**，这些函数不能独立发布到游戏。

## 第二/第三阶段初始化

第二张回调表的 `51ADB0` 包装器把五个回调参数转交给 `6661A0`。helper 接受 RDX=entity、R9=描述符数组、entry RSP+28=count 指针、entry RSP+30=list 指针；两个栈偏移为十六进制。它从全局输入对象读取十一项值，在五张保存结构对应的合成表中转换索引，生成 56 bytes secondary，同时申请并填充同样的 56-byte 临时数据，追加四个 16-byte 描述符。四个 hash 为 `DFE49C6F`、`64E318CE`、`AE5166E8`、`AA7E1B9E`，类型为 `10,10,10,1`，数据偏移为 `0,24,32,52`（后两列十进制）。未知键的零/FFFFFFFF 回退保留原行为。

保存的 `581320` 调用者将描述符数组放在 `RBP+30`，cookie 位于 `RBP+830`，因此这条调用路径的空间是 `800` bytes，即 128 个描述符。候选要求初始 count ≤124；数组、count/list 指针和输入对象指针非零，并核对 map 身份及迁移后指针。该容量只依据这个固定调用者，不能作为其他调用者的通用约定。指针可读、list 有效及缓冲生命周期仍由调用方负责。

第三张表的 `51ADE0` 包装器调用 `664430`，把目标 primary 的前 44 bytes 设为 FF，保留余下 36 bytes。它随后重置 `3797960` 的 128×16-byte 表、更新 `3798180` 头部、清零 `3797550` 的 1,024-byte 区域及 `348BA88`。验证执行整个保存包装器；这些全局操作没有被错误移入仅负责 primary 的 helper 映像。

属性映像为 1,988 bytes、三条函数表记录；重置映像为 1,176 bytes、五条记录。属性保留 `EHANDLER|UHANDLER`、120-byte 栈帧和 frame+64 cookie，handler 通过本地跳板连接保存的 `21044A0 → 21044C0 → 2088770`。Windows 三种 unwind flag 均验证，真实保存 GS 处理器只在模拟内存执行；最后的 cookie 检查是显式契约替身。

两次属性分配失败对照（原版/候选）证实：分配器返回零时，secondary 前 24 bytes 已更新，随后写地址零故障，描述符尚未追加。此路径也未实现回滚。helper 预检拒绝不写栈或数据；经过原包装器的拒绝已存在 64/48-byte 调用帧，但不改变数据，不能用普通布尔返回代替非返回拒绝路径。

## 直接入口与批次重置

新增五个入口保留各自真实 ABI，不能把已登记 callback 的参数约定直接套上去：

| 映像 | 原 RVA | 参数和效果 | 映像 bytes / 函数表记录 |
|---|---|---|---:|
| `direct_dense` | `666710` | RDX=entity，R8=flags；密集插入 | 1,084 / 2 |
| `direct_append` | `6667D0` | RDX=entity；追加尾部 | 616 / 2 |
| `direct_remove` | `666A00` | RDX=entity；返回 EAX=原 entity+10 的 DWORD | 1,016 / 2 |
| `reset_control` | `6642C0` | DL 写 S+1；DL=0 时批次重置 dense primary | 1,164 / 7 |
| `reset_dense` | `665EC0` | 批次重置 dense primary，最后 S[0]=1 | 984 / 5 |

`reset_control` 的零标志路径将每个密集项 primary 的前 44 bytes 设为 FF、最后 32 bytes 归零，中间 4 bytes 保留；非零标志只改控制字节。`reset_dense` 只将前 44 bytes 设为 FF，余下 36 bytes 保留。其他三组数组和计数均不变，不能把两种重置合并成全记录清零。

批次预检保留 DL，在任何栈/数据写入前核对所有 T 个有效指针、map 占用数和身份。查找使用保存函数的乘法散列、八桶线性探测与遇空停止规则，每次最多探测八桶；不是只扫描有没有这个 ID。测试保留了“ID 存在但 home bucket 已空”的反例，并验证另一种有效散列乘数。实体和 map 可读、外部同步仍由调用方保证。

直接入口收据通过 **2,288 次执行**：170 次四槽原版、2,049 次八槽候选成功、69 次无写入拒绝。包含八组传递真实模拟状态的“移除→两种批次重置→同一 ID 密集重加入”，检查移除后的 map 序号和数据重排。另有 **4,148 个 Windows 回溯上下文**、五个损坏回溯负对照、13 个有效定位和 302 个拒绝定位。回溯检查使用三种 Windows unwind flag；候选仍仅在 Unicorn 执行。

## 待加入分区的原版反例

来源锁还固定了 **`666850`** 的完整代码和三段 unwind，供原版重播；它现在对应新的 `promote_pending` 候选，算法与原版的有损路径不同。在全部 35 种 `0≤P≤D≤T≤4` 的合成状态中，10 种 `P<D<T` 状态会丢失有效身份：原函数先将 P 行复制覆盖到 pending 行，再调用搬移器，最终出现重复指针，T/D/P 的更新本身却正常。其余 25 种状态保留身份。

另已定位创建后的两个直接读者：`ADDD85`（root `ADDC10`）和 `B62400`（root `B62210`）仍从旧 `S+70` 指针数组取实体，再调用 `664430`。只改重置 helper 不能覆盖这两条调用者读取；必须一起迁移并验证整段调用作用域。`117D830` 的四处全局引用在已检查窗口内只读取 `S+1` 控制字节，这不构成该函数全路径的数组访问排除证明。

该结果只证明保存函数在这些明确构造状态下的行为；尚未证明真实调用者允许全部状态。因此不能把“计数已经变成八”当成记录正确。新的无损转换见下节。下一步要将 owner `576CF0` 的内联循环与它连接，核对真实调用前提及整个调用范围的写入排除，再补 registry/其余直接读写覆盖。只生成 helper 并不能覆盖 owner 的内联路径。

## 保留身份的待加入批次转换

第十四个映像 `EP_COMPONENT33_PROMOTE_PENDING` 以原 `666850..6669D6` 为固定来源，但使用新算法替换有损主体；不是原指令的逐条重定位。接口为 `RCX=S`，返回 `EAX=T`。

对旧 `i=D..T-1`，将 i 行与当前 P 行的 pointer、primary、secondary 交换，再交换 map 中对应两项的序号，最后 `P++`。P==i 时跳过交换。循环结束设置 D=T；最终 P=旧 P+旧 T-旧 D，T 和高水位不变。原 prefix 顺序保持，原 pending 顺序进入新 prefix，原 dense 非 prefix 身份完整留在后段。

新映像为 824 bytes，仅使用易失整数寄存器和 XMM0–1，不建立栈帧、不调用 helper、不申请临时资源。全部代码由一条 leaf 回溯记录覆盖。byte 行、实体 flag、未使用槽位与外部资源生命周期保持不变。

进入前检查 RCX/global 均指向绑定 S、0≤P≤D≤T≤8、全部 active 身份及原始八桶探测语义；原 dense flag 必须与 prefix 一致，所有 pending 实体的 bit0 必须已由调用方设为 1。这个检查来自转换后 prefix 的一致性要求，**真实调用者是否满足它仍未证实**。指针可读写和完整调用期间的独占访问仍由 owner 保证；循环中 P 可能暂时超过旧 D，直到最后 D=T，不允许并发观察中间状态。

本轮收据确认 858 次功能执行与 168 个 Windows 回溯上下文通过。验证在两个模拟基址覆盖全部 165 种八槽计数组合及重复调用，另有 27 组保留真实模拟字节的“追加→批次转换→移除新身份→同 ID 密集重加入”。原版 35 种四槽状态的 25 种无损状态逐字节一致，10 种有损状态保留为负对照。三个故意破坏数据交换、map 更新和计数更新的变异体均须被独立身份/数据断言识别。Windows 用正确 leaf 记录与虚构 16-byte 栈帧记录对照；游戏代码只在 Unicorn 执行。

下一连接点已从保存 capture 核对：owner `576CF0..58131E`，完整 SHA-256 为 `d698b632ac6f51e7441873b27dd5baa6364ff3c41751dee8fe718755df26d931`。`577B16..577B61` 为元件33的内联循环，`577B3C`、`577B4D` 仍分别调用 mover；`577B61` 准备下一元件地址，`577B68` 写 D，`577B6B` 调用 `6689A0`。完整 owner 内的直接跳转扫描未发现由窗口外跳入该循环的边；这个有限结果不排除其他函数或间接入口。迁移时必须核对 RSI/RDI/返回状态、原 owner 的回溯范围和后续调用，不能仅 hook `666850` 后宣称 owner 已覆盖。

## 接口边界与拒绝

`ep_component33_image_build` 只产生代码、回溯元数据和函数表，不读取地址指向的数据，不分配或封存可执行内存，也不发布 hook。地址无效、区域重叠或相对跳转超出范围时，输出清零并返回错误。

生成映像在原函数序言之前检查绑定头部、容量、计数关系、map 布局，以及插入/删除/搬移所需的身份条件。拒绝发生在任何栈写入、数据写入及 map helper 调用之前，`R10D` 给出原因。拒绝出口必须支持调用方的内部栈帧，不能把它接到一个普通返回布尔值的函数。

调用方仍负责实体指针可读、分类标志与分区一致、完整 map 状态、数据生命周期、并发排空和整次操作的事务性。检查并不是任意地址的安全读取器，也不是整个创建流程的补偿器。

## 混合分区的插入与移除修复

`T = total`、`D = dense`、`P = prefix`，满足 `0≤P≤D≤T≤8`。registered/direct 四个插入与移除映像使用以下修复；批次转换另有独立算法。

- 密集插入：如果 `D<T`，先把旧 D 的 pointer、primary、secondary 和 map 序号搬到旧 T，再执行原有的 prefix 搬移、新项插入及计数更新。原本即将被覆盖的第一个 pending 项因此保留。
- 移除密集项：先执行原有 prefix/dense 压实与计数递减；如果新 `D<T`，再把新 T（旧最后 pending 项）搬到新 D。包括 D 从 1 降至 0 的边界。移除 pending 项继续使用原尾部压实。
- 四入口在任何栈或数据写入前，检查全部有效实体、原有八桶 bounded probe、map 序号及 dense 区的 prefix flag。一致性错误会无写入拒绝。可读性、调用方同步与新增实体 flag 的正确设置仍是外部前提。

这是真正新增的保留身份算法，不是原函数不变重定位。它保留既有搬移器不复制 byte、不清空来源槽、不分配或清理资源的行为，不能代表资源生命周期已闭合。

插入的补充调用分别位于原 `51AC99` / `666739` 前；移除的 dense 路径由 `51AD97` / `666A71` 跳到补充块，pending 分支保留。原序言与 `RSP-0x28` 帧不变，补充调用使用 body `RSP+0x38`（entry `RSP+0x10`）暂存参数或返回值，避开 callee shadow space 和保存的非易失寄存器。新增块纳入原主体回溯范围。`direct_remove` 继续返回原 entity+10 的 DWORD。

所有候选密集插入覆盖 `0≤P≤D≤T≤7` 和两种 flag；移除覆盖 `1≤T≤8` 的全部分区与全部目标槽。除了按顺序建模，还独立检查存活身份集合不丢失、不重复、map 与有效行一一对应、每个存活身份的 primary/secondary 保留。直接入口另有 280 组使用真实前一步模拟数据的“混合分区移除→同 ID 密集重加入”，包括满八槽和 D 降至零。旧有八组批次重置连续场景仍保留。

20 个四槽原版混合插入对照均复现身份丢失；核心原版密集移除反例也继续保留。这些结果证明合成状态下的缺陷和修复，不证明真实调用者会产生所有这些状态。

## 实际验证范围

核心收据记录 **1,507 次功能执行**（含原版和拒绝对照）、**2,768 个 Windows 回溯上下文**、19 组有效映像定位及 177 组拒绝定位；四个破坏回溯记录的负对照均被识别。

核心验证包含四槽原版与八槽候选的普通/密集插入、全部槽位的搬移、全部合法分区的移除、满表碰撞、八种删除后以同一身份重新插入、容量与错误身份拒绝，以及更换模拟基址。自有 DLL 的字节输出与参考重定位一致；非法地址输出必须全部清零。

Windows 验证只把候选字节放入 `PAGE_READWRITE`，注册临时函数表后对模拟上下文调用 `RtlVirtualUnwind`，不原生执行保存的游戏指令。四个映像各保留一个破坏回溯记录的负对照；正确记录须恢复调用者栈和非易失寄存器。实际执行指令的地方仅为 Unicorn 模拟内存。

分类收据另有 **776 次功能执行**：70 次四槽原版、674 次八槽候选成功、32 次写入前拒绝。包含全部 `0 ≤ P ≤ D ≤ T ≤ 8` 的有目标分类组合、五组进入后退出连续操作、直接 helper ABI 与第二个模拟基址。另检查 10 组有效定位、80 组拒绝定位、**12,845 个不同 Windows 回溯上下文**，以及两个根序言损坏和两个条件序言偏移回归负对照。四次分配失败反例单列，未计入 776 次正常/拒绝执行；条件序言的两个修正对照复用已有上下文，未重复计入 12,845。

创建分派另有 18 次联合执行：两个模拟基址、已有 0–8 项、参考九元件顺序。第一张表使用当前 C++ 元件 33 和 C++ 名册 239；第 1–8 项经过两个插入器，第九项先被元件 33 拒绝。其他元件及后续属性/资源接口仍是明确标注的替身。原外层在拒绝之前已经写入资源记录等数据，联合测试继续核对并保留这一未解决问题。

初始化收据另外通过 **280 次执行**：50 次四槽原版、194 次八槽候选成功、36 次预检拒绝；覆盖零键、已知键、未知键、混合输入、count=124 边界以及五组分类→属性→重置连续操作。另有 10 组有效定位、94 组拒绝定位、**7,698 个不同 Windows 回溯上下文**、两个损坏元数据负对照、四次 GS 正常/坏 cookie 模拟、两次包装器数据不变拒绝和两次空分配反例。后四类单列，不重复计入 280 次。

创建分派另新增 **20 次初始化整合执行**，保留上述 18 次核心场景：两个基址各执行已有 0–8 项及第八项无效资源类型。第 1–8 项实际经过元件33三张回调表，生成四个描述符并转交资源契约替身，完成第三阶段重置。无效资源仍留下 `7FFF` 序号；第九项仍在第一阶段拒绝且保留此前外层写入。创建总场景为 80 次，仍不是角色分配证明。

## 下一位接手者的顺序

1. 读取上述核心收据、创建分派收据及 [status.json](status.json)，确认源码和构建指纹相符。
2. 优先连接 `576CF0` 的内联批次路径，并核实 `666850` 的调用方 flag、并发与生命周期契约，再覆盖其他 byte/secondary 写入、owner 直接访问与 registry 访问。分类和第二/第三回调已完成本文所列离线验证，但分类/属性分配失败补偿、调用方 flag/通知以及从旧四槽数据建立 `B` 的生命周期和所有权仍待实现。
3. 完成这一族函数后，再提供 READY 准备、封存和统一发布接口；当前十四个映像不得单独激活，不计入已存在的十七个共同入口。
4. 对剩余固定四槽元件建立相同的读写闭合验证，并在 `FDC140` 写入前完成共同接纳或实现全部副作用补偿。保留资源类型无效时的 `7FFF` 残留反例。
5. 按[容量与原生 UI 计划](CAPACITY_UI_PLAN.zh-CN.md)继续生产身份、内存所有权和角色控制/复制；第五人全流程与原生 UI 先验收，再完成八人主要里程碑，并按证据扩展人数。任何游戏访问都需要新的明确授权；本轮授权余额为零。

## 离线复验

从仓库根目录使用已固定的上游与工具链运行 [完整离线构建步骤](HANDOFF.zh-CN.md)。单独验证已有的自有 DLL 时：

```powershell
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path (Get-Location) 'work/hellforge-zig-cache'
$env:ZIG_LOCAL_CACHE_DIR = Join-Path (Get-Location) 'work/hellforge-zig-local-cache'
py -3.12 -B hellforge_multiplayer/tools/validate_component33_images.py `
  --library hellforge_multiplayer/build/component33_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe `
  --out work/component33-validation.json
py -3.12 -B hellforge_multiplayer/tools/validate_component33_classify.py `
  --library hellforge_multiplayer/build/component33_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe `
  --out work/component33-classify-validation.json
py -3.12 -B hellforge_multiplayer/tools/validate_component33_initialize.py `
  --library hellforge_multiplayer/build/component33_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe `
  --out work/component33-initialize-validation.json
py -3.12 -B hellforge_multiplayer/tools/validate_component33_direct.py `
  --library hellforge_multiplayer/build/component33_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe `
  --out work/component33-direct-validation.json
py -3.12 -B hellforge_multiplayer/tools/validate_component33_transition.py `
  --library hellforge_multiplayer/build/component33_image_test.dll `
  --zig work/hellforge_toolchain_20261025/zig-x86_64-windows-0.17.0/zig.exe `
  --out work/component33-transition-validation.json
```

该命令编译和运行自有回溯测试程序，读取仓库保存的代码。`installable`、`runtime_verified`、`multiplayer_verified`、`public_release_allowed` 继续为 false。
