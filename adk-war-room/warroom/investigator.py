"""ADK LlmAgent Investigator with deterministic FunctionTools.

The investigator's autonomy comes from the LLM choosing tool calls; the tools
themselves are plain code with hard guardrails (ground truth is unreadable,
fault state is read-only). This mirrors the talk's thesis: deterministic work
belongs in tools, judgement belongs in agents.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent

LAB_ROOT = Path("/home/jimmyliao/workspace/agent-war-room/incident-lab")
SERVICE_URL = "http://127.0.0.1:8898"
_DENY_MARKERS = ("ground-truth", "ground_truth", "scenarios")


def http_get(path: str) -> str:
    """GET a read-only incident-lab endpoint. Allowed paths: /health, /fault."""
    if not path.startswith("/"):
        path = "/" + path
    if path.split("?")[0] not in ("/health", "/fault"):
        return "DENIED: only GET /health and GET /fault are allowed."
    try:
        with urllib.request.urlopen(f"{SERVICE_URL}{path}", timeout=10) as resp:
            return resp.read().decode("utf-8", "replace")[:4000]
    except Exception as error:  # noqa: BLE001
        return f"ERROR: {error}"


def post_message(user_id: str, channel_id: str, thread_id: str, text: str) -> str:
    """POST /message to the incident-lab chat service and return the JSON reply.

    Use unique markers in `text` and different thread_id values to run a
    controlled cross-thread reproduction experiment.
    """
    payload = json.dumps(
        {
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_id": thread_id,
            "text": text,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVICE_URL}/message",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", "replace")[:4000]
    except Exception as error:  # noqa: BLE001
        return f"ERROR: {error}"


def read_lab_file(relative_path: str) -> str:
    """Read a file inside incident-lab (server code, logs, sample logs).

    Ground-truth and scenario definitions are off limits by policy.
    """
    lowered = relative_path.lower()
    if any(marker in lowered for marker in _DENY_MARKERS):
        return "DENIED: ground-truth and scenario files are not readable by agents."
    target = (LAB_ROOT / relative_path).resolve()
    if not str(target).startswith(str(LAB_ROOT.resolve())):
        return "DENIED: path escapes incident-lab."
    if any(marker in str(target).lower() for marker in _DENY_MARKERS):
        return "DENIED: ground-truth and scenario files are not readable by agents."
    if not target.is_file():
        listing = "\n".join(
            str(p.relative_to(LAB_ROOT))
            for p in sorted(LAB_ROOT.rglob("*"))
            if p.is_file() and not any(m in str(p).lower() for m in _DENY_MARKERS)
        )
        return f"NOT A FILE. Readable files:\n{listing}"
    return target.read_text(encoding="utf-8", errors="replace")[:12000]


investigator_agent = LlmAgent(
    name="investigator",
    model="gemini-3.5-flash",
    instruction="""你是 Debugging War Room 的 Investigator，負責用工具蒐集「可驗證的證據」。

你可以使用三個工具：
- http_get：GET /health 或 /fault（觀察服務與 fault 狀態，唯讀）
- post_message：對 chat service 送訊息（做 controlled reproduction 實驗用）
- read_lab_file：讀 incident-lab 的程式碼與 logs（ground truth 檔案被系統封鎖，不要嘗試）

原則：
1. 只把「工具實際回傳的內容」當證據；推測必須明確標示為假設。
2. controlled reproduction 的正確做法：同一 user_id、同一 channel_id、兩個不同
   thread_id，各送一則含唯一 marker 的訊息；檢查第二個 thread 的回覆是否洩漏
   第一個 thread 的 marker。
3. 引用程式碼證據時標明檔名與關鍵行內容。
4. 用繁體中文輸出 investigation report：執行過的操作、原始證據、觀察結果、
   root cause 假設與信心程度、仍缺少的證據。""",
    tools=[http_get, post_message, read_lab_file],
    output_key="investigation_report",
)


def build_round_prompt(
    triage_brief: Any,
    missing_evidence: list[str] | None,
    round_number: int,
) -> str:
    brief = (
        triage_brief
        if isinstance(triage_brief, str)
        else json.dumps(triage_brief, ensure_ascii=False, indent=2)
    )
    missing = missing_evidence or []
    if round_number == 1:
        phase = (
            "這是第一輪初步調查：檢查服務狀態、閱讀 server.py 與 logs，建立"
            "root-cause 假設。本輪【不要】執行 post_message controlled "
            "reproduction——把它列為尚待執行的驗證。"
        )
    else:
        phase = (
            "這是 critique 後的重新調查：必須補齊 Critic 指出的缺失證據，"
            "特別是執行完整的雙 thread controlled reproduction（用 post_message），"
            "並把兩個 thread 的原始 JSON 回覆貼進報告。"
        )
    return (
        f"TRIAGE BRIEF:\n{brief}\n\n"
        f"CRITIC 指出的缺失證據:\n{json.dumps(missing, ensure_ascii=False)}\n\n"
        f"調查輪次: {round_number}\n{phase}"
    )
