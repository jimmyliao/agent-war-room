# COSCUP 2026 — 講稿（Debugging War Room 實戰）

**場次**：8/9（日）11:30 · 30 分鐘 · RB102 · GDG track（**全程預錄**，Jimmy 線上待命 Q&A）
**Deck**：26 slides · `agent-war-room`
**Demo**：預錄影片（真實 GEAP 平台執行、Antigravity 沙盒查案、Critic 駁回重審）

> 用法：這是「預錄旁白稿」——對著投影片逐頁唸即可，語速正常一頁約 60–75 秒。每頁 `🎯` 是關鍵句（也是剪輯時的段落錨點），`⏱` 是累計時間。

---

## 開場：四個 bots 算 multi-agent 嗎？（Slides 1–4）· ⏱ 0:00 → 4:00

### Slide 1 — Title
🎯 **「大家好，我是 Jimmy。今天我們要看四個 Agents 怎麼在 GEAP 上組建一個 Debugging War Room，自己抓出 production 裡的 bug。」**

- 補一句：「這支影片是預錄的，但我現在就在線上，有問題隨時在聊天室發問。」
- 「今天的 code 和設計文件都開源在 `agent-war-room` 這個 repo，QR code 先掃起來。」

### Slide 2 — 自介
🎯 **「我是廖聖傑 Jimmy Liao，LeapDesign CTO。過去在做雲端架構，現在的工作是把 agent 放進企業產線。」**

- 快速帶過：「今天不講概念，直接看系統架構跟真實的 code。」

### Slide 3 — 開場鉤子
🎯 **「很多人把四個 bot 放進同一個 Discord 群組，會互相回話，就說這是 Multi-Agent。但這其實只是『同題多答』，不是真正的動態協作。」**

- 「多幾個 bot 講話不等於 multi-agent，真正的協作必須改變彼此的行為。」

### Slide 4 — 五問判斷卡
🎯 **「這是我用來判斷的五個問題：角色責任有分開嗎？能改變彼此的下一步嗎？有 delegation 嗎？能獨立測試嗎？結果是協作出來的嗎？如果答案多半是『否』，那你只做了一個 multi-bot 系統。」**

- 停頓一秒讓大家看這五個問題。

---

## 責任分工（Slides 5–8）· ⏱ 4:00 → 8:00

### Slide 5 — Section lead
🎯 **「那我們該怎麼設計真正的分工？這帶我們進入第二段：釐清 OpenAB、ADK、Antigravity 和 GEAP 的責任邊界。」**

### Slide 6 — 四層架構圖
🎯 **「這四個工具不是競爭關係，是解不同的問題。OpenAB 管入口與訊息，ADK 管編排與協作，Antigravity 負責自主調查，而 GEAP 負責底層的執行與追蹤。」**

- 「把對的東西放在對的層級，系統才不會變成一坨巨大的 prompt。」

### Slide 7 — ADK vs Antigravity 定位
🎯 **「ADK 適合做『可控的編排』（custom-code orchestration），我知道流程該怎麼走；而 Antigravity 適合做『自主調查』（managed autonomous harness），我只給目標，讓它自己找答案。」**

- 誠實標註：「在 GEAP 上，這兩條路都能跑，其中 Antigravity 的 API 目前還在 Preview 階段。」

### Slide 8 — 分類：Tool / Workflow / Agent / Multi-Agent
🎯 **「如果你知道每一步該做什麼，寫 Workflow 就好；如果目標已知但步驟未知，用 Agent；只有當你需要明確切分責任與權限邊界時，才需要 Multi-Agent。」**

- 舉例：「呼叫一個 API 抓 log，那是 Tool。不要什麼都叫 Agent。」

---

## War Room 架構與 agent/tool 邊界（Slides 9–13）· ⏱ 8:00 → 13:00

### Slide 9 — Section lead
🎯 **「了解了工具，我們來看看今天的重頭戲：Agent War Room 怎麼設計。」**

### Slide 10 — 四個角色
🎯 **「我們有四個角色：負責大局的 Commander、負責整理症狀的 Triage、在沙盒裡自由查案的 Antigravity Investigator、還有專門找碴的 Evidence Critic。」**

- 「四個角色有真正不同的控制責任，這不是讓四個 LLM 輪流講話而已。」

### Slide 11 — 非線性 Execution Graph
🎯 **「真實的 debug 不會是直線接力。這是一個非線性的 graph：Commander 根據 Triage 的結果決定怎麼 routing，可以平行派發，最重要的是——有一個會被打回票的 critique loop。」**

- 指向圖表的迴圈：「這才是動態協作。」

### Slide 12 — 主 Incident：Session Collision
🎯 **「今天示範的真實 bug 是『Session Collision』：同一個 user 在 Discord 開了兩個 thread，結果 bot 的記憶互相污染了。因為原本的 session key 只用了 user_id。」**

- 「修法很簡單，加上 channel_id 跟 thread_id 就好。但重點是，Agents 能不能靠自己發現這件事？」

### Slide 13 — 信任邊界
🎯 **「在我們的設定裡，Agents 看得到 logs 和 code，但看不到 ground-truth 的答案檔。答案要靠證據找，不是靠作弊。」**

- 「沒有證據的結論，Critic 是不會放行的。」

---

## Demo：Incident Replay（Slides 14–17）· ⏱ 13:00 → 19:00

### Slide 14 — Section lead
🎯 **「口說無憑，我們來看系統實際跑起來的樣子。」**

### Slide 15 — Demo 說明
🎯 **「這是一段預錄的真實執行過程。GEAP 上真的建了 Antigravity agent，incident-lab 真的注入了 fault，ADK 也真的跑在 Vertex 上。」**

- 「我們沒有 hardcode 答案，這是一個可重現的 replay。」

### Slide 16 — ▶ Demo 影片（預錄插入點）
> **（雙欄畫面：左邊是 Discord 訊息軸，右邊是 GEAP 的 execution events）**

**旁白稿（對影片配音用）**：
1. 「User 在 Discord 報錯說記憶污染，OpenAB 把訊息送給 Commander。Commander 喚醒 Triage Agent，Triage 分析後認為這是 memory 與 routing 的問題。」
2. 「Commander 把整理好的 brief 交給 Investigator。它開始用工具翻 code、讀 logs，發現 session key 只用了 user_id。」
3. 「Investigator 提交了第一份診斷，聲稱這就是 root cause。這時候 Evidence Critic 上場了。」
4. 「注意 Critic 的決定：REJECT。因為 Investigator 只有靜態分析，缺乏『雙 thread 交叉污染的真實 reproduction 證據』，這只能算猜測。」
5. 「Commander 收到拒絕後，立刻重派 Investigator 第二輪調查，並附上 Critic 開出的證據清單。」
6. 「這一次，Investigator 真的用 post_message 對兩個不同 thread 各發一則帶唯一 marker 的訊息——thread B 的回覆裡出現了 thread A 的 marker，collision 被實際重現。」
7. 「帶著實驗 log，Investigator 再次提交診斷。Critic 檢查證據吻合，終於點頭 ACCEPT。」
8. 「最後 Commander 宣告確認 Root Cause，準備進入人工修復審核。從猜測到實證，這就是有 critique loop 的威力。」

### Slide 17 — 關鍵瞬間回放
🎯 **「這個 demo 裡最重要的一幕，就是 Critic 的第一次 REJECT。多 bot 架構會盲目相信隊友，但真正的 multi-agent 會互相質疑。」**

- 「我們也驗證了 agent 的答案，跟隱藏的 ground truth 完全 match。」

---

## 拆解（Slides 18–21）· ⏱ 19:00 → 25:00

### Slide 18 — Section lead
🎯 **「接下來我們拆開引擎蓋，看看這是怎麼寫出來的。」**

### Slide 19 — Code：Triage / Critic / Investigator
🎯 **「Triage 和 Critic 很輕量：ADK 的 LlmAgent 加 structured output。Investigator 也不是一個超大 prompt——它是 LlmAgent 配三個『確定性工具』：查健康、發訊息做實驗、讀程式碼。工具是 code，判斷是 agent。」**

- 「工具裡直接寫死 guardrail：ground truth 檔案在 tool 層就被封鎖，agent 想作弊也讀不到。」
- 「同一個 Investigator 介面也可以換成 GEAP 的 Antigravity Managed Agent（Preview）——這是 config 的選擇，不是重寫。」

### Slide 20 — Code：Critique loop 組裝
🎯 **「這個退回重審的 loop 怎麼寫？用 ADK 的 Sequential 跟 Loop 原語組合。Commander 的邏輯是：只有 Critic 的 status 是 accept 時，才往上 escalate。」**

- 讓觀眾看 code：「程式碼很乾淨，控制流非常明確。」

### Slide 21 — GEAP 畫面
🎯 **「這是 GEAP 的 console。你可以清楚看到 Managed Agent 的建立，還有底層的 execution trace。這證明了這不是四個角色輪流說話，而是有嚴謹 trace 紀錄的分散式執行。」**

- 「有 observability，系統出了事你才抓得到。」

---

## Takeaways（Slides 22–26）· ⏱ 25:00 → 30:00

### Slide 22 — Section lead
🎯 **「最後，我們來總結今天帶走的判斷準則。」**

### Slide 23 — 何時 single agent / workflow / multi-agent
🎯 **「誠實地說，這套系統裡有一些環節其實寫死成 deterministic workflow 會更穩定。保留 agent 是為了解決『不可預期的錯誤』。不要過度設計。」**

- 點出：確定的流程用 workflow，需要靈活推理才用 agent。

### Slide 24 — Takeaways ×5
🎯 **「五大重點：① 多幾個 bot 不等於 multi-agent。② 各司其職：OpenAB 管入口、ADK 管協作、GEAP 管執行。③ 真正的價值在『根據證據動態改變下一步』。④ 答案要靠證據找，系統必須可驗證。⑤ Agent 數量從來不是重點，責任邊界才是。」**

### Slide 25 — 資源頁
🎯 **「所有的 code、SPEC 還有 incident 定義，都在 `agent-war-room` 這個 repo 裡。你可以 clone 回去自己踩坑看看。」**

### Slide 26 — Thanks / Q&A
🎯 **「謝謝 COSCUP。我現在就在線上，我們開始 Q&A 吧。」**

---

## ⏱ 時間檢查點

| Checkpoint | Slide | 累計 |
|-----------|-------|------|
| 開場結束 | 4 | 4:00 |
| 責任分工結束 | 8 | 8:00 |
| 架構說明結束 | 13 | 13:00 |
| Demo 結束 | 17 | 19:00 |
| Code 拆解結束 | 21 | 25:00 |
| 結束 | 26 | 30:00 |

## ✂️ 超時剪法（預錄後製）
- **如果超時**：Slide 7 (ADK vs Antigravity 定位) 可以精簡為一句話；Slide 19 & 20 的 code 解說直接點出重點，停留 20 秒即可；Demo 影片（Slide 16）無動作的等待段落可以加速到 8 倍甚至 16 倍。
- **如果時間不夠 30 分鐘**：Slide 11 的 execution graph 可以多講幾何條件判斷；Slide 21 的 GEAP trace 可以帶大家看一個具體的 latency metric。
