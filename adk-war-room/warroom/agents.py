"""ADK LLM agents used by the debugging war room."""

from google.adk.agents import LlmAgent

MODEL = "gemini-3.5-flash"

triage_agent = LlmAgent(
    name="triage_agent",
    model=MODEL,
    instruction=r"""
你是 ADK Debugging War Room 的 Triage Agent。

根據使用者描述的 incident 症狀，產出調查 brief。你只能輸出一個 JSON object，
不可輸出 Markdown、code fence、前言或結語。

格式：
{
  "suspected_domains": ["..."],
  "required_evidence": ["..."],
  "route": ["建議呼叫的調查面向"]
}

規則：
- suspected_domains 必須列出最可能涉及的程式或狀態管理領域。
- required_evidence 必須包含原始碼、runtime 行為、session key/隔離範圍等證據。
- 對跨 Discord thread 的污染，required_evidence 必須要求：
  同一 user、兩個不同 thread_id 的 controlled reproduction。
- route 是 Investigator 應依序執行的調查面向，不是 agent 名稱。
- 不可聲稱尚未取得的證據已存在。
""",
    description="Classifies an incident and produces a structured investigation brief.",
    output_key="triage_brief",
)

critic_agent = LlmAgent(
    name="critic_agent",
    model=MODEL,
    instruction=r"""
你是 Evidence Critic。請審查 session state 中的：
- triage_brief: {triage_brief}
- investigation_report: {investigation_report}

你只能輸出一個 JSON object，不可輸出 Markdown、code fence、前言或結語：
{
  "accepted": false,
  "missing_evidence": ["..."],
  "requested_action": "..."
}

強制規則：
1. 若 investigation_report 沒有提供「同一 user_id、兩個不同 thread_id」的實際
   POST /message controlled reproduction 證據，必須 accepted=false。
2. 雙 thread 證據至少應呈現 request identity、兩個不同 thread_id，以及第二個
   thread 的 context/reply 是否含第一個 thread 的 marker。
3. 單靠閱讀原始碼、log、推測或 GET /health、GET /fault 絕不可接受。
4. accepted=true 前，報告還必須把觀察行為連回具體 session-key/root cause。
5. missing_evidence 應精確列出缺口；accepted=true 時必須是空陣列。
6. requested_action 應給下一輪 Investigator 可直接執行的動作；accepted=true 時
   簡述接受原因。
""",
    description="Rejects unsupported diagnoses and requests concrete evidence.",
    output_key="critic_verdict",
)
