# ADK Debugging War Room

本機 ADK incident-debugging MVP：

1. `triage_agent` 產出 structured investigation brief。
2. agy Investigator 執行初步調查。
3. `critic_agent` 檢查 controlled reproduction 證據。
4. Reject 時 Commander 進入 `REINVESTIGATING`，最多三輪。
5. Accept 時推進至 `RESOLVED`。
6. Public Event Projector 將 v1 events 寫入 `runs/<incident_id>/events.jsonl`，
   並在 console 顯示 timeline。

所有 ADK LLM agent 使用 Vertex AI 上的 `gemini-3.5-flash`。Investigator
使用本機：

    agy --model gemini-3.1-pro --effort low --print-timeout 10m -p "<prompt>"

程式不讀取 incident ground truth，且 Investigator prompt 明確禁止存取
`incidents/*/ground-truth.json`。Investigator 只能 GET `/fault`，不可改變 fault
mode。

## 前置條件

- incident-lab 已在 `http://127.0.0.1:8898` 執行。
- `agy` 位於 `PATH`。
- 已具備你自己 GCP 專案的 Vertex AI ADC 權限（`export GOOGLE_CLOUD_PROJECT=<your-project>`）。
- 一個已安裝 `google-adk` 的 Python 環境（venv / uv）。

## 執行

以下指令皆從 `adk-war-room/` 目錄執行：

    uv run python run_incident.py

自訂症狀：

    uv run python run_incident.py \
      "同一 user 在不同 thread 看到彼此訊息"

指定 incident ID：

    uv run python run_incident.py \
      --incident-id INC-003

## 輸出

Console 應展示：

    Triage → Investigate → Critic(Reject) → Reinvestigate → Critic(Accept)

事件檔位於：

    adk-war-room/runs/<incident_id>/events.jsonl

每行皆符合 `agent-war-room.public-event.v1`。Allowed event types：
`incident.started`, `agent.delegated`, `investigation.progress`, `evidence.found`,
`review.accepted`, `review.rejected`, `approval.required`, `incident.resolved`,
`incident.failed`。
