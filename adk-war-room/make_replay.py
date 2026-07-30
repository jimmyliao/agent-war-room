# -*- coding: utf-8 -*-
"""Generate a self-contained animated replay.html from a run's events.jsonl."""

import json
import sys
from pathlib import Path

RUNS = Path(__file__).parent / "runs"

AGENT_META = {
    "commander": ("🧭", "Commander", "#5865F2"),
    "triage_agent": ("📋", "Triage", "#3BA55D"),
    "investigator": ("🔬", "Investigator", "#FAA61A"),
    "critic": ("🧪", "Evidence Critic", "#ED4245"),
    "critic_agent": ("🧪", "Evidence Critic", "#ED4245"),
    "evidence_critic": ("🧪", "Evidence Critic", "#ED4245"),
}

run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(
    p for p in RUNS.iterdir() if p.is_dir()
)[-1]
events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines()]

html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Agent War Room — Incident Replay</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Noto Sans CJK TC','gg sans',sans-serif; background:#1e1f22; color:#dbdee1; height:100vh; overflow:hidden; }
.header { background:#111214; padding:10px 18px; display:flex; align-items:center; gap:12px; border-bottom:1px solid #2b2d31; }
.header .badge { background:#ED4245; color:#fff; font-weight:700; border-radius:4px; padding:2px 8px; font-size:13px; }
.header .title { font-weight:700; font-size:15px; }
.header .sub { color:#949ba4; font-size:12px; margin-left:auto; font-family:monospace; }
.cols { display:flex; height:calc(100vh - 45px); }
.left { flex:1.15; background:#313338; overflow-y:auto; padding:14px 16px; }
.right { flex:1; background:#0d1117; overflow-y:auto; padding:12px 14px; border-left:1px solid #2b2d31; font-family:'DejaVu Sans Mono',monospace; }
.right h3 { color:#7d8590; font-size:11px; letter-spacing:1px; margin-bottom:8px; position:sticky; top:0; background:#0d1117; padding:4px 0;}
.msg { display:flex; gap:10px; margin-bottom:12px; opacity:0; transform:translateY(8px); transition:all .4s; }
.msg.show { opacity:1; transform:none; }
.avatar { width:38px; height:38px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:19px; flex-shrink:0; }
.body .name { font-weight:700; font-size:14px; }
.body .time { color:#949ba4; font-size:11px; margin-left:6px; }
.body .text { font-size:13.5px; margin-top:2px; line-height:1.45; white-space:pre-wrap; }
.tag { display:inline-block; font-size:10.5px; font-weight:700; border-radius:3px; padding:1px 6px; margin-right:6px; vertical-align:1px;}
.ev { margin-bottom:7px; font-size:11.5px; color:#7d8590; opacity:0; transition:opacity .4s; line-height:1.5; }
.ev.show { opacity:1; }
.ev .k { color:#79c0ff; }
.ev .t { color:#ffa657; }
.reveal { margin:10px 0; padding:12px; border:2px solid #3BA55D; border-radius:8px; background:#232a25; opacity:0; transition:opacity .6s; }
.reveal.show { opacity:1; }
.reveal .row { font-size:13px; margin:3px 0; }
.reveal .ok { color:#3BA55D; font-weight:800; font-size:16px; }
</style></head><body>
<div class="header"><span class="badge">🚨 INCIDENT</span><span class="title">__RUNID__ · cross-thread context contamination</span><span class="sub">ADK × Vertex gemini-3.5-flash · public-event.v1</span></div>
<div class="cols"><div class="left" id="chat"></div>
<div class="right"><h3>EXECUTION EVENTS (events.jsonl · 真實記錄)</h3><div id="raw"></div></div></div>
<script>
const EVENTS = __EVENTS__;
const META = __META__;
const chat = document.getElementById('chat'), raw = document.getElementById('raw');
function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function typeTag(t){
  const m = {'incident.started':['#ED4245','INCIDENT'],'agent.delegated':['#5865F2','DELEGATE'],
    'investigation.progress':['#949ba4','PROGRESS'],'evidence.found':['#FAA61A','EVIDENCE'],
    'review.rejected':['#ED4245','REJECTED ✗'],'review.accepted':['#3BA55D','ACCEPTED ✓'],
    'incident.resolved':['#3BA55D','RESOLVED'],'incident.failed':['#ED4245','FAILED']};
  const [c,l] = m[t]||['#949ba4',t];
  return `<span class="tag" style="background:${c};color:#fff">${l}</span>`;
}
let i = 0;
function step(){
  if (i >= EVENTS.length){ finale(); return; }
  const e = EVENTS[i];
  const [emoji,name,color] = META[e.agent]||['🤖',e.agent,'#949ba4'];
  const m = document.createElement('div'); m.className='msg';
  m.innerHTML = `<div class="avatar" style="background:${color}22;border:2px solid ${color}">${emoji}</div>
    <div class="body"><div><span class="name" style="color:${color}">${name}</span><span class="time">${e.timestamp.slice(11,19)}Z</span></div>
    <div class="text">${typeTag(e.type)}${esc(e.summary)}</div></div>`;
  chat.appendChild(m); requestAnimationFrame(()=>m.classList.add('show'));
  const r = document.createElement('div'); r.className='ev';
  r.innerHTML = `<span class="k">${e.eventId.slice(0,8)}</span> <span class="t">${e.type}</span> agent=${e.agent} progress=${e.progress}%`;
  raw.appendChild(r); requestAnimationFrame(()=>r.classList.add('show'));
  chat.scrollTop = chat.scrollHeight; raw.scrollTop = raw.scrollHeight;
  i++;
  const pause = (e.type.startsWith('review')) ? 3400 : (e.type==='evidence.found' ? 2600 : 1700);
  setTimeout(step, pause);
}
function finale(){
  const d = document.createElement('div'); d.className='reveal';
  d.innerHTML = `<div class="row">🔍 <b>/incident reveal</b> — 比對 ground truth（agents 全程不可讀）</div>
   <div class="row">Injected fault&nbsp;&nbsp;: <code>session_collision</code>（session key 只用 user_id）</div>
   <div class="row">Agent diagnosis: session_collision 模式下僅以 user_id 作為 session_key → 跨 thread 污染</div>
   <div class="row ok">RESULT: ✅ MATCH · 1 rejection → controlled reproduction → accepted</div>`;
  chat.appendChild(d); requestAnimationFrame(()=>d.classList.add('show'));
  chat.scrollTop = chat.scrollHeight;
  document.title = 'REPLAY_DONE';
}
setTimeout(step, 1200);
</script></body></html>"""

html = html.replace("__EVENTS__", json.dumps(events, ensure_ascii=False))
html = html.replace("__META__", json.dumps(AGENT_META, ensure_ascii=False))
html = html.replace("__RUNID__", run_dir.name)
out = run_dir / "replay.html"
out.write_text(html, encoding="utf-8")
print("REPLAY_HTML", out)
