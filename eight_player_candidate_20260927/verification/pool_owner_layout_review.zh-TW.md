# Owner layout 獨立審查與修正

## 範圍

獨立代理 `singleton_review` 只讀核對 `pool_owner_layout.lua`、其測試及契約。範圍為固定 lifecycle 證據的 305／325 地址投影、285 個固定 S、完整玩家 record span、retired storage、輸入界限及 coverage 與 bytes 驗證的分工。沒有操作遊戲程序或重新擷取。

## 發現與重現

受審原始碼 SHA-256：`b304b80250d412d7369fc9fb84f44800a39b7ba28b89ec03ecbfd58fb5a2aafa`。

原 `check_coverage` 已拒絕額外 S 跨入停用的原 storage，卻未拒絕其覆蓋目前玩家 storage 的非 S 欄位。例如新玩家 records 基址 P，第一個已知 S 為 `[P+28h,P+A0h)`；額外 S `[P-50h,P+28h)` 覆蓋 record 頭部，卻不碰任何已知 S。

審查代理以只讀 Lua 合成案例確認原版 layout 與 snapshot 均可接受。作者先加入回歸案例、再執行舊 Lua，重現前後邊界八個 subcase 被錯誤放行。這是合成資料檢查缺陷，不是實際遊戲資料破壞的觀察。

## 修正與驗證

對不在 expected 清單的 owner，新增整個 S 與目前 `player_records` 完整 span 的相交檢查，命中回 `player_storage_overlap`。預期玩家 S 本身保留正常接受行為。

- Test 21：原四筆、搬移四筆、搬移八筆的 record 頭部及尾端，共六個邊界案例。
- Test 22：搬移四／八筆外側相鄰、只接觸邊界的地址仍允許。
- Test 23：有效合成 S bytes 在 snapshot 可接受時，layout 仍拒絕其覆蓋 record 非 S 欄位的前後兩例。

修正後完整 [23 組測試](pool_owner_layout_tests.json) 通過，零 failures／errors。獨立代理再讀修正與三項新增測試，確認封閉原反例；沒有要求追加修正。主代理另讀 guard 與案例，交付時核對原始碼／報告 SHA。

最終原始碼 SHA-256：`5e640ff48b495ea9cb89b74eedd0ee2ed84f8e40c7682c409f064ca07b3165b4`。

最終測試 SHA-256：`3b63e706aa4a6327f1dac955173da4c360dd984d1353bd6f619db5969ff58595`。

## 保留限制

只涵蓋已知直接生命週期清單及有限已知區域。八份布局是候選投影；成功未證明新地址已配置、所有 aliases 已搬移或資源已回收。Coverage 不驗 bytes，後續須把同一 packet 交給 snapshot validator；兩者都沒有提供執行期來源、同步、原生執行或多人成功證據。
