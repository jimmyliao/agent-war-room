# Agent War Room: 今晚 MVP 落差與衝刺分析 (GAP-TONIGHT)

## 1. M0-M5 里程碑：今晚合理範圍

基於目前技術現實 (ADK + Vertex ADC 可用，Antigravity API 未知，OpenAB 不串，本機 `agy` 為 fallback)，今晚 MVP 的合理範圍設定如下：

* **納入範圍 (In Scope):**
  * **M0 (部分):** Event schema 與 Session-collision fixture 定義。
  * **M1 (核心):** Local incident & orchestration，實作 Local ADK Commander, Triage, Critic。
  * **M2 (降級):** Investigator 先使用本機 `agy CLI` 或 mock 作為 fallback 替代品，暫不強求 Managed Agents API。
* **明確排除 (Out of Scope for Tonight):**
  * **M3 (GEAP 部署):** 全面於本機執行，不部署至 Agent Runtime。
  * **M4 (OpenAB 串接):** 不做真實 Discord/OpenAB ACP 整合，僅將 Event 輸出至 Console。
  * **M5 (評估與錄影):** 今晚只求 MVP 跑通，不進行正式 Metric 評估與影片錄製。

## 2. 現有骨架 vs SPEC 的差距清單

目前各模組目錄僅有 `README.md`，幾乎為空殼。以下為今晚需補齊的缺口：

* **`adk-war-room/` [缺]**
  * 缺 ADK Orchestrator (Commander) 狀態機邏輯。
  * 缺 Triage Agent 與 Evidence Critic 的 prompt 與結構化輸出 (Vertex ADC)。
* **`antigravity-agent/` [缺]**
  * 缺呼叫本機 `agy CLI` 的 wrapper/adapter (替代未知的 Managed API)。
* **`incident-lab/` [缺]**
  * 缺 Session collision 測試場景的 fixture (包含假 logs / source code snippet)。
* **`openab-adapter/` [部分]**
  * 缺 Mock Event Projector (將系統內部事件轉為 Public Event JSON 輸出)。
* **`experiments/` [缺]**
  * 缺今晚展示用的啟動腳本 (`run_mvp.js` 或類似腳本)。
* **`skills/` [缺]**
  * 缺 Investigator 所需的基礎 Debugging instructions (供 `agy` 讀取)。

## 3. 今晚 MVP 驗收 Checklist

(限制 10 項內，針對 SPEC 驗收標準的子集)

1. [ ] 可透過本機腳本啟動單一 Incident (Session Collision)。
2. [ ] ADK Triage 成功產出包含問題分類的 JSON。
3. [ ] 啟動 Investigator (使用 `agy` fallback)，並產生初步的錯誤推論 (未進行雙 thread 重現)。
4. [ ] Evidence Critic 成功辨識缺乏控制組重現，並回傳 Reject 決策。
5. [ ] Commander 接收 Reject，成功觸發第二輪調查 (Re-investigation)。
6. [ ] 第二輪 Investigator 回報包含雙 thread 重現證據的結果。
7. [ ] Evidence Critic 驗收通過 (Accept)。
8. [ ] Commander 成功將狀態推進至 `RESOLVED`。
9. [ ] 系統全程透過 Mock Event Projector 輸出符合格式的 Public Event Timeline。
10. [ ] Console Trace 清楚展示 Triage -> Investigate -> Critic(Reject) -> Investigate -> Critic(Accept) 的流程。

## 4. Public Event Contract 與 Incident State Machine 速查

**Incident 狀態機 (State Machine):**
`NEW` -> `TRIAGING` -> `NEEDS_INPUT` / `INVESTIGATING` -> `REVIEWING` -> `REINVESTIGATING` (迴圈) -> `AWAITING_APPROVAL` / `RESOLVED` / `INCONCLUSIVE` / `FAILED` / `CANCELLED`

**Public Event Contract (v1) JSON 範例與規範:**
* **Schema:** `agent-war-room.public-event.v1`
* **Allowed Types:** `incident.started`, `agent.delegated`, `investigation.progress`, `evidence.found`, `review.accepted`, `review.rejected`, `approval.required`, `incident.resolved`, `incident.failed`
* **關鍵欄位速查:**
```json
{
  "schema": "agent-war-room.public-event.v1",
  "incidentId": "INC-003",
  "sessionId": "...",
  "eventId": "...",
  "timestamp": "...",
  "agent": "evidence_critic",
  "type": "review.rejected",
  "summary": "Controlled reproduction is missing.",
  "progress": 65
}
```

## 5. 明確可以「砍掉不做」的部分

(今晚與未來兩週內皆非必要的範圍)

1. **真實雲端部署:** GEAP Agent Runtime 部署、GCP Observability 整合 (僅靠本地 console/JSON logs)。
2. **Discord/OpenAB 真實串接:** 捨棄真實 webhook/ACP 實作，以 Mock UI 或 Console 取代。
3. **Managed Agents API 完整對接:** 若建立與互動 API 測試失敗，兩週內皆以 CLI Fallback 或模擬層取代。
4. **Secondary Incidents (403, Timeout, Schema Drift):** 捨棄實作，僅專注於主打的 Session Collision。
5. **進階沙盒隔離限制:** 放棄實作 Antigravity 的嚴格 Network/FS 沙盒，信任本地執行環境。
6. **多 Incident 並發處理 (Concurrency):** 今晚只求跑通單一事件，不處理複雜的 Session Lock 與排隊。
