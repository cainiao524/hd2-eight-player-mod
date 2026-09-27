# FileDiver 離線分析

狀態：已解析參考資料，仍有維修／玩法缺口。
來源提交：`bf0ce329db3cf0043994eb717ea86433c303cb36`
解析器：`1.0.0`

副武器記錄 27；已知射擊元件 20；彈頭 350。
前三範圍排除類型 38，其中多彈丸 32。

來源為 FileDiver 編譯時內嵌參考；檔案夾名稱不證明目標遊戲版本。
附件的個別候選覆寫不等於已確認的最終裝備配置。數字 ID 不等於穩定武器身分。
需另核對 15 個 runtime 錨點、游標、所有權、碰撞時機；不得只換 hash 啟用。
原始表及 analysis.json 留本機，不放入公開模組／工具包。

## 缺口

- `game_build_correspondence_unestablished` ：An embedded FileDiver snapshot, directory name or successful parse does not prove correspondence to the installed game.
- `runtime_review_required` ：Review all 15 runtime anchors, allocation cursor, owner chain, slot layout and collision timing independently.
- `gameplay_not_verified` ：Static classification and offline comparison are not self-hit/healing or performance evidence.
- `attachment_precedence_unresolved` 006e44327bb953fe：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 02cd7321cd8445f5：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 03e67a19b07c6523：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 05d8d8c073b9d502：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 05e4e5c2db6e44a2：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 076dd5d4f4360204：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 0807aea5217e4767：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 085c1edb038ec24e：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 0f83639ab8c86165：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 11c27d3babb38956：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` 1312b769f47256d9：Entity projectile follow-up collision/owner/timing is not established.
- `entity_collision_unverified` 14d5d4506056c7a4：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` 14d5d4506056c7a4：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 186ea95de7306b1a：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 1a437158e1b8d2a1：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 1abbff60d26ba391：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 2152d5147b0ac418：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` 25aa2fd4643cf4ee：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` 25aa2fd4643cf4ee：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 263817187b7ce092：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 26e40437ea275296：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 27ee1ed8f6fb6356：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 295beb26dc4f8ff1：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 2c66c201b2543d2c：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 2e9d0bdc48b09e60：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 30061f91af477f5e：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 3575aabc5f1f9326：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 35a61296619cc47e：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 372481e910c05a76：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 3828e2051aa9e897：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 3c86e871923f3970：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 3d4970d1c4e640ee：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 416d053372c4e433：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 41eac4a03987faa0：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 43cb1033961a2276：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 46183b50961d1328：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4ba41b6f9f405cc2：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4c786785c79d44e7：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4d58c77087b774c5：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4dbd74f49c8ffc13：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4e310b1fe4c52b52：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4e4a613eb9bf5c24：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4f749e2ee26f532d：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` 4f8a477e577aaba9：Default customization ID is absent from item table.
- `missing_default_attachment` 4f8a477e577aaba9：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` 4f8a477e577aaba9：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 4fb0f8c02f55c82b：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` 52e4334e6a128caf：Default customization ID is absent from item table.
- `missing_default_attachment` 52e4334e6a128caf：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` 52e4334e6a128caf：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 587878fb76f4b9b1：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` 5990123d142b16cb：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` 5990123d142b16cb：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 5ebaea70c0d060b9：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 5fecab819f96a3e8：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 65cd4325ba23f3c6：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` 6bf1164ea3829a23：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` 6bf1164ea3829a23：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 6cfcc7f8801a0266：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 708ea298c82093d0：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 72170a55a1f37ff1：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 7b06196e90154c88：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 7b75e5132ffd4ca6：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 7e3145a5baa4b948：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` 80932fa0ed6901d3：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` 80932fa0ed6901d3：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 80f1a156d9fa1e36：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` 821d035aa47e3e75：Entity projectile follow-up collision/owner/timing is not established.
- `entity_collision_unverified` 824b7e0c4c879eb5：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` 84354339522c932d：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 8645f167b3c813a2：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 89c5493e08ca4207：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 8a307bd1811a5fe9：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` 8aff7f0793a5bced：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` 8d3d52a3b2f19402：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 90ddc374f4e3d756：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 94bd931b5fb4ee95：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 9571ca51f0daf35b：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 968211c0033dce64：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` 9f80d67a12a7e40f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` a0532c3616528cbf：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` a0532c3616528cbf：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` a1379c8c41a10e22：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` a1bdb3a13e3633dd：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` a32621e3bde13379：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` a6a735accb4a327f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` a7ee1ebf58fcdf1f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` a8a91eb54892b6b2：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` a8a91eb54892b6b2：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` a8cffb316f0b5c5f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` a955c4ea6f6d4203：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` aa69a60d74a3ec54：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` b16c9d490aa59b77：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` b2b5e0d185605f9e：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` b43235dbd493750c：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` b43235dbd493750c：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` b6aff2195568767f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` b729a2ba153bcaed：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` b9606c5aab32c3c2：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` b9606c5aab32c3c2：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` b9c209b4f99b5335：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` bc242702fb46b7e7：Entity projectile follow-up collision/owner/timing is not established.
- `missing_default_attachment` bc29613666df696b：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` bc29613666df696b：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` bcc2177439d231be：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` bde1f2534280300d：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` be70ee0d8d44028e：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` c12a34f375bd5a87：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` c780bcd79547da0f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` c85f576d5e086147：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` ca4bbef63c869c18：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` cc786f6491fe7e65：Entity projectile follow-up collision/owner/timing is not established.
- `missing_default_attachment` cc786f6491fe7e65：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` cc786f6491fe7e65：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` cd00bdc1149c2928：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` cdf28be026bb7d84：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` ce063aa33d95a812：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` cf5f176e0e322be1：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` cf8934ff6567a42d：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` cf8934ff6567a42d：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` d323de60855898ac：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `missing_default_attachment` d53ee03481ae73fd：Default customization ID is absent from item table.
- `attachment_precedence_unresolved` d53ee03481ae73fd：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` d54b9505c0f72873：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` dbb6c961c59fadc1：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` dcd1c835407ef7ba：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` e5796355a8fd67e0：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` e6d932be83729076：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` e8d5f49ad7780e54：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `entity_collision_unverified` e91f569c2ad8af01：Entity projectile follow-up collision/owner/timing is not established.
- `attachment_precedence_unresolved` e91f569c2ad8af01：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` eea5e3cef1e12c14：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` f0338468dcdb6a6c：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` f49227a0630a3f7f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` f992ce97577c8a7f：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` fb3a19078694708a：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
- `attachment_precedence_unresolved` fc13460592ca79aa：Individual attachment deltas are candidates; order, eligibility and composition are not proven.
