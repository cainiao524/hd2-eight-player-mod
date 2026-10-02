# 1277920：兩個 roster 讀取與無已證拒絕結果的 mask 迴圈

2026-09-28，依 P3 工作清單在 v0.14 收尾後推進。成品需求是搬移八格 roster 後，剩餘 reader 仍讀同一 entity 的資料。本次要決定完整 reader 需要改哪幾處，以及是否需要為 network index4–7 擴大 mask 或修改拒絕邏輯。固定完整 body、必要 leaf 與原迴圈的可觀測效果後停止此項查核，下一步轉為候選實作；不展開其他 callee 樹。

## 證據及範圍

[重播程式](roster_mask_reader_replay.py)只讀倉庫內已保存的 capture，逐檔核原 SHA-256 與 capture identity；沒有程序查詢或新擷取。[固定 evidence](roster_mask_reader_evidence.json)包含完整 `1277920..1277F7B`：1627 bytes、390條指令、48個局部分支、20個RIP參照、12個direct calls、1個indirect call，以及3個同root的chained unwind fragments。

完整原body SHA-256：`aecf466c012f2e9ba64787a5108b1807753f55166b484d7a0c21c71a21e5d1ca`。另固定40-byte `585B80..585BA8` leaf與52-byte跳轉表；表的13個DWORD均為RVA `585B9B`。leaf沒有captured unwind entry，因此依已知direct-call入口和實際CFG辨認code/data邊界，沒有將表解碼成程式。

## 共同 B 必须改兩處

`127796B` 將 global3326468 讀到 R11=S，`[entry RDX+Ch]` 的entity ID經 S map查到ordinal。這個ordinal同時驅動：

| 原位點 | 原讀取 | 八格目的 |
|---|---|---|
| `12779F5` | `COMISS XMM5,[S+ordinal×70h+12Ch]`，primary第24h欄 | `B+64h+ordinal×70h` |
| `1277A06` | `MOV R8D,[S+ordinal×20h+3B4h]`，property第Ch欄 | `B+58Ch+ordinal×20h` |

既有property inventory只列第二處，不能據此只搬property。Primary浮點值大於0或unordered時，原`JB`跳過network／mask讀取；零與負值則可能進入。須保留此flags語義。這兩個operand之外，R11在`1277A0E`改載global33269C0的另一物件，之後不能把同名register的其他來源都當作roster。

## Mask沒有已證的玩家拒絕結果

新物件的`+Ch`給mask數量，`+48h`給DWORD mask陣列。`1277A2F BT EAX,R8D`使用network DWORD；FFFFFFFF被顯式跳過。Register BT以低5位選DWORD中的bit，因此4–7原本就在寬度內，32與0同bit，不能將此一般DWORD運算當成只允許四人的比較。

所有迴圈離開路徑都匯入`1277A3C`。之後兩次`585B80`的RCX分別固定為`D00000003h`、`E00000003h`；leaf將低DWORD3索引到同一case，返回高DWORD13／14。它在使用前覆寫EDX與R8，原mask迴圈的EDX次數沒有以返回值或store傳往後續。R9 sentinel及浮點XMM暫存器則由這個實際leaf保留，不能套用「所有volatile都任意破壞」的替身契約。

[前綴probe](roster_mask_reader_probe.py)及[結果](roster_mask_reader_probe.json)做了24次原指令前綴觀察：network 0、3、4、7、31、32、FFFFFFFF各配三種mask（第一筆不符、第二筆不符、全部符合），另測primary正／負值及mask count0。每個network的三種mask在`1277AA3`前具有完全相同GPR、EFLAGS和XMM狀態；實際mask讀取次數符合原分支，非stack只發生原input+10h計時更新。48次巢狀585B80執行不另加總。

此結果限穩定合成資料及指定前綴。它沒有證明迴圈可在live環境刪除，也未觀察完整return或後續callback。候選應保留原迴圈；目前沒有依據增加mask容量或發明第五人拒絕修補。Mask producer的live有效性仍是外部契約，但不因本次reader需求泛查其全域來源。

## 下一個實作決策及未解契約

1. 候選須把兩個陣列operand接入共同B，保留S map／header、原miss fallback與完整剩餘流程。普通missing會設定input+4及+8後返回；不能將所有miss直接改成未說明的拒絕。
2. 原`127795A`在查roster前已累加input+10h。若候選承諾拒絕前無非stack副作用，guard必須放在此store之前，保留RCX、RDX及XMM2浮點步長；在命中後才拒絕會留下計時更新。須明示空key、無效ordinal、錯誤binding及合法missing各自政策。
3. 全body後段從global3326D20取得另一張map、`+6Ch` count與`+110h` pointer陣列。其ordinal和roster/network index不同；不可把這張表改接roster B。另有32筆、stride E8h的ring操作，32不是玩家容量證據。
4. 完整clone需保存原12個direct calls、indirect callback、cookie與三段unwind的語義。585B80已核有限內部ABI；927050、後續ring／事件calls、資源有效性及callback穩定性仍須在候選驗證中明列必要契約。不能把本前綴probe標成完整reader通過。

這份調查未發射新候選，也未升版至v0.15。v0.14仍為已完成的6054F0離線交付；24次前綴觀察不加入149組／4,314次交付套件總數。Sidecar生命週期、hook／unwind／拒絕整合、平台加入、角色建立及五至八帳號全流程仍未完成。

## 重現

工作區根目錄執行，指定全新輸出檔名：

```powershell
& 'C:\Program Files\Python312\python.exe' -B five_player_feasibility_20260927/roster_mask_reader_replay.py --output NEW-mask-evidence.json
& 'C:\Program Files\Python312\python.exe' -B five_player_feasibility_20260927/roster_mask_reader_probe.py --evidence NEW-mask-evidence.json --output NEW-mask-probe.json
```

預設capture路徑為倉庫內`evidence/existing-code-evidence-25480438`；可用replay的`--evidence`明確指定其他保存目錄。兩個程式均拒絕覆寫輸出。
