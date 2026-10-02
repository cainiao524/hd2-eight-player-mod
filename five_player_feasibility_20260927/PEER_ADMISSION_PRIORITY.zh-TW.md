# 2026-09-29：外部分析對照與第五人接納優先順序

使用者提供了Player Clone、EntityNetworkDataArray、NetworkOverrideComponent、hot join及四項AI Director倍率的分析，建議優先追查第五個peer是否能被session接受並取得player index4。本記錄將該建議與已保存Steam build25480438證據對照；本次只讀工作區文件，沒有新擷取、遊戲程序存取或執行測試。

## 採納的研究方向

P1平台／session接納與P2有效角色建立仍是整體可行性門檻。接下來評估加入鏈時，優先回答：**第五個獨立帳號是否被接受、是否取得唯一index4、是否在各端形成同一confirmed-peer記錄，以及是否走到有效角色建立。** 八人名冊reader候選提供必要資料存取配套，但其數量與離線通過次數不能代替這條加入鏈的證據。

已有原指令充分定位的四人判斷不重新泛搜。需要釐清的目標是尚未閉合的session結果、發布／接收關係與生命週期，不以`MaxPlayers`、hotjoin名稱或型別宣告代替實際路徑。

## 分析中的線索與目前可採用程度

| 提供的線索 | 可支持的方向 | 仍不能推出 |
|---|---|---|
| Player Clone含正常玩家元件 | 同類實體可能可重複建立，值得追蹤實際player資源路徑 | 舊模板ID `5556372446766824087`等同目前原生caller的實際載入模板，或各元件都有八份原生儲存 |
| `EntityNetworkDataArray.entities`是array | schema未直接寫固定四筆 | 運行期配置、peer路由、ownership與消費者没有四人上限；也未證明第五個受控玩家能跨端同步 |
| component索引18對應NetworkOverrideComponent | 在相同版本、相同起算與enum順序成立時，可作網路特殊處理的查找線索 | 僅凭索引或`dummy [ignore]`證明具體native行為及八人能力 |
| teleporter及hotjoin欄位／枚舉 | 有中途加入與補齊世界狀態的設計線索 | 可同時容納五至八人；四人房間補進一名玩家也需要這些機制 |
| AI Director四項人數倍率 | 值得獨立核對第5–8人的索引、clamp及fallback | 已知第五人會越界，或必定沿用第四項；須讀實際consumer |

提供的文字未附上述舊資料的來源檔、提交或版本。本輪有限本地文字搜尋未找到這幾個schema名稱及倍率欄位的既有研究記錄；未全面解析binary datalibrary，因此不將「未找到文字」視為資料不存在。原模板ID、enum位置、倍率數值先列為待核線索，未提升為當前build已核實結論。

## 已經定位的具體限制

1. **game.dll 本機 join handler 的接納／容量路徑與 index 分配。** [協定與索引記錄](protocol_index_and_wire_notes.md)已固定`108BC70`加入handler：容量判斷在`108C18F..108C1D6`，獨立分配器在`108C3B3..108C403`只掃host+100h四個byte flags，分配0..3並寫peer記錄+14h的DWORD。這是本機原指令證據，不是已解析的平台服務端接納結果；`108DDC7/108DE09`的下游介面與非同步完成回應仍未解析。
2. **房主與客戶端儲存。** 同一記錄及[REPORT](REPORT.zh-TW.md)指出host四筆peer／大型／pending陣列不能原地延長；client的confirmed-peer第5筆會從+150h開始，覆蓋另一個實際使用的結構。這些是現有布局下的相鄰固定區，需搬移／重排並更新生命週期。index的4-byte descriptor只表示欄位寬度不阻止編碼4–7，不等於完整wire／接收鏈與其容量已證明。
3. **平台本機列舉。** [平台成員布局](platform_member_layout_findings.zh-TW.md)證明在僅提高count／容量而保留原起點時，第5個8-byte ID會寫入+1B78h並覆蓋結果與控制欄位；至少兩個內嵌平台物件使用這個布局。提高列舉上限必須配合儲存及所有已知讀取端。
4. **角色建立有獨立gate。** [完整本地建立流程](local_player_creation_gate_findings.zh-TW.md)證明`1086460/1086469`對已找到的本地peer network index作unsigned `<4`。index4–7進fallback，略過此root唯一已確認的player-resource call `FDC140`，即使後續仍能到達共同peer同步尾部。不能把「已分配index4」或「ready流程繼續」當成角色已生成。

因此採納「優先解決peer/index」，同時保留角色gate與儲存改造為必要配套。不能由通用entity容器和hotjoin線索，降低已證多個四筆玩家元件／roster原生儲存與角色路徑的必要性。

## P1下一個有限動作

先沿既有證據表核對尚未閉合的連線邊，不重做已完成的容量／index指令確認：

- 從`108D9F0`的`108DDC7/108DE09` game-session介面呼叫，明確列出已知參數、可見返回／狀態消費者、缺少的間接目標和非同步完成來源。兩處可見64-bit玩家ID，不能憑此假定服務已接收network index。
- 接上host confirmed通知`108C760→BE4910`及本地`B90B20`路徑；遠端wrapper `BABA80`與event hash `4804FCF4`的runtime註冊關係仍未直接閉合。逐項列「發送了什麼、接收後存在哪裡、何時標記完成」。
- 若調整批次join請求，先處理`BA8CC0`的固定stack record：已有證據顯示6個qword會碰到cookie；不把「八人總容量」等同「每次必須傳八個ID」，也不把現有callback當成已證八項wire格式。
- 成功標準是形成可審閱的接納／index發布／confirmed接收變更契約，或具體指出需要哪個未保存介面／完成事件。到此收束，不泛搜其他SDK或把擷取授權自行延伸。

平台建立參數的八使用者／八裝置形狀仍為有前提的SDK對照，不能證明八名遊戲玩家被接受。P1若缺所需保存資料，繼續P3已定位的1277920兩處改接與其他可離線完成工作；不以重跑相同模型填補平台證據。

## AI Director獨立列項

P6補入`player_count_multipliers`核查：先固定同build資產及schema，再沿實際consumer確認count來源、索引算式、陣列長度與0／5–8／超界輸入的處置。只有實際consumer證明clamp或安全fallback，才能說5–8沿用第四項；若是直接索引，才依證據設計延長資料或邊界處理。通過條件包含真實資產適用性和後續多人負載／難度行為。

既有[NATIVE_PLAYER_COUNT](../eight_player_candidate_20260927/NATIVE_PLAYER_COUNT.zh-TW.md)處理94C9C0／94BE10的count及設定範圍；目前沒有證據將它與這個AI Director倍率欄位連起來，不能說v0.14已覆蓋該風險。

## 授權與完整目標

前三次擷取已用完。第四次待答覆的EXE+1AE380是角色建立下游，不能當作取得其他session介面資料的授權。本輪只更新研究決策；沒有發射或安裝新patch。八帳號同任務全流程仍是最終目標，平台加入、角色、同步、生命週期、撤離結算及可安裝交付均須各自驗證。
