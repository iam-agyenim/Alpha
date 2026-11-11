"""Animated workflow visual (HTML/SVG/JS component) that replays a WorkflowRun's real, timestamped events.

Nodes pulse while running and turn green when done; data packets travel along the edges when one step hands
results to the next; the event log streams in with timestamps; clicking a node shows what it received and sent.
Theme: white, green (#0B6B3A) and black.
"""
import json

import streamlit.components.v1 as components

from belt_defect.agents.workflow import EDGES, NODES

ICONS = {"intake": "database-import", "security": "shield-lock", "model": "brain", "orchestrator": "route",
         "quality": "shield-check", "logistics": "truck-delivery", "commercial": "briefcase",
         "verify": "shield-search", "approval": "user-check", "outputs": "file-certificate"}
POS = {"intake": (125, 80), "security": (385, 80), "model": (645, 80), "orchestrator": (905, 80),
       "quality": (905, 262), "logistics": (645, 262), "commercial": (385, 262), "verify": (125, 262),
       "approval": (385, 444), "outputs": (645, 444)}
PATHS = {("intake", "security"): "M232,80 H278", ("security", "model"): "M492,80 H538",
         ("model", "orchestrator"): "M752,80 H798", ("orchestrator", "quality"): "M905,126 V216",
         ("quality", "logistics"): "M798,262 H752", ("logistics", "commercial"): "M538,262 H492",
         ("commercial", "verify"): "M278,262 H232", ("verify", "approval"): "M125,308 V444 H278",
         ("approval", "outputs"): "M492,444 H538"}


def _summaries(run) -> dict:
    """Short human-readable lines per step for the detail panel."""
    o, s = run.outputs, {}
    sec = o.get("security_input", {})
    s["intake"] = [f"Batch: {run.batch_label}"] + [e["message"] for e in run.events if e["step"] == "intake"
                                                   and e["kind"] == "done"]
    s["security"] = [f"Rows received: {sec.get('rows_received', '—')}", f"Valid: {sec.get('rows_valid', '—')}",
                     f"Quarantined: {sec.get('rows_quarantined', '—')}",
                     f"Missing readings (flagged): {sec.get('rows_with_missing_measurements', '—')}"] + \
                    [f"• {i}" for i in sec.get("issues", [])]
    m = o.get("model", {})
    s["model"] = [f"Screenings scored: {m.get('screenings_scored', '—')}", f"Predicted defects: {m.get('predicted_defects', '—')}",
                  f"High Risk aircraft: {m.get('aircraft_high_risk', '—')} · Medium: {m.get('aircraft_medium', '—')}",
                  f"Top aircraft: {', '.join(m.get('top_aircraft', []))}",
                  f"Tool most linked to risk: {m.get('tool_most_linked_to_risk', '—')}", m.get("model", "")]
    r = o.get("orchestrator", {})
    s["orchestrator"] = [f"To Quality & Safety: {r.get('to_quality', '—')}", f"Then: {r.get('then', '—')}"]

    def agent_lines(step, fn):
        res = o.get(step) or {}
        out = res.get("output") or {}
        if res.get("error"):
            return [f"Error: {res['error']}"]
        if not out:
            return ["Not run yet"]
        lines = [out.get("summary", "")] + fn(out)
        lines.append("Number check: " + ("passed" if not res.get("ungrounded") else "review " + ", ".join(res["ungrounded"])))
        lines.append("Tools: " + ", ".join(t["tool"] for t in res.get("tools", [])))
        return lines

    s["quality"] = agent_lines("quality", lambda q: [f"• {x['priority']} {x['aircraft']} {x['engine']}: {x['reason']}"
                                                     for x in q.get("inspections", [])[:10]] +
                               [f"• {t['tool']}: {t['action']}" for t in q.get("tool_actions", [])])
    s["logistics"] = agent_lines("logistics", lambda lg: [f"• {p['station']}: need {p['belts_needed']}, stock "
                                                          f"{p['belts_in_stock']}, order {p['belts_to_order']}"
                                                          for p in lg.get("parts_plan", [])] +
                                 [f"• {c['tool']} → {c['slot']} (loan {c['loan_tool']})"
                                  for c in lg.get("calibration_plan", [])])
    s["commercial"] = agent_lines("commercial", lambda c: [
        f"Plan cost: ${c['cost_summary']['action_cost_usd']:,} vs predicted defect cost at risk "
        f"${c['cost_summary']['predicted_defect_cost_at_risk_usd']:,}",
        f"To approver: {c.get('recommendation_to_approver', '')}", f"Customer note: {c.get('customer_note', '')}"])
    s["verify"] = [f"{k}: {v}" for k, v in (o.get("security_output") or {}).items()]
    a = run.approval or {}
    s["approval"] = ([f"{a['decision']} by {a['approver']} at {a['time'][11:19]} UTC"] + ([a["comment"]] if a.get("comment") else [])
                     if a else ["Waiting for the maintenance manager's decision (below the diagram)"])
    wo = (o.get("outputs") or {}).get("work_orders", [])
    s["outputs"] = [f"{len(wo)} work orders issued"] + [f"• {w['id']} {w['type']}: {w['target']} ({w['priority']})"
                                                        for w in wo[:12]] if wo else ["Issued after approval"]
    return s


def render(run, play_id: str, start_index: int = 0, height: int = 1010):
    """start_index = first event to animate (earlier events are applied instantly)."""
    payload = {
        "nodes": [{"id": n, "label": label, "sub": sub, "kind": kind, "icon": ICONS[n], "x": POS[n][0], "y": POS[n][1]}
                  for n, label, sub, kind in NODES],
        "edges": [{"from": a, "to": b, "d": PATHS[(a, b)]} for a, b in EDGES],
        "events": run.events, "status": run.status, "summaries": _summaries(run), "meter": run.meter,
        "run": {"id": run.run_id, "batch": run.batch_label, "started": run.started, "finished": run.finished},
        "start": start_index, "play": play_id,
    }
    data = json.dumps(payload, default=str, ensure_ascii=False).replace("</", "<\\/")
    components.html(TEMPLATE.replace("__DATA__", data), height=height, scrolling=False)


TEMPLATE = r"""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css">
<style>
:root{--g:#0B6B3A;--gt:#E8F3EC;--gm:#9CCBB0;--k:#0B0B0B;--k2:#4A4F4C;--k3:#8A918D;--line:#E3E7E4;--bg:#FFFFFF;}
*{box-sizing:border-box} body{margin:0;font-family:Inter,"Source Sans 3",system-ui,sans-serif;color:var(--k);background:var(--bg)}
.top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:4px 2px 10px}
.chip{font-size:12px;border:1px solid var(--line);border-radius:999px;padding:4px 10px;color:var(--k2);background:#fff;white-space:nowrap}
.chip b{color:var(--k);font-weight:600}
.chip.live{border-color:var(--g);color:var(--g)} .chip.live::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--g);margin-right:6px;animation:blink 1s infinite}
.ctl{margin-left:auto;display:flex;gap:6px}
.btn{font:inherit;font-size:12.5px;border:1px solid var(--k);background:#fff;color:var(--k);border-radius:8px;padding:5px 11px;cursor:pointer}
.btn.on,.btn.dark{background:var(--k);color:#fff}
.prog{height:3px;background:var(--line);border-radius:3px;overflow:hidden;margin-bottom:8px}
.prog i{display:block;height:100%;width:0;background:var(--g);transition:width .3s ease}
.canvas{position:relative;width:100%;aspect-ratio:1120/530;border:1px solid var(--line);border-radius:16px;
  background-image:radial-gradient(#E6EBE7 1px,transparent 1px);background-size:22px 22px;overflow:hidden}
svg.edges{position:absolute;inset:0;width:100%;height:100%}
.edge{fill:none;stroke:#CDD5CF;stroke-width:2;stroke-dasharray:5 6}
.edge.live{stroke:var(--g);stroke-width:2.5;stroke-dasharray:9 7;animation:flow 1.1s linear infinite}
.packet{fill:var(--g)} .packet-ring{fill:none;stroke:var(--g);stroke-opacity:.35}
.node{position:absolute;background:#fff;border:1.5px solid var(--line);border-radius:14px;padding:11px 12px 8px 12px;overflow:hidden;
  display:flex;flex-direction:column;gap:1px;cursor:pointer;transition:border-color .35s,background .35s,transform .2s,box-shadow .35s}
.node:hover{transform:translateY(-2px)}
.node .hd{display:flex;align-items:center;gap:9px;min-width:0} .node .hd>div:nth-child(2){min-width:0;flex:1}
.ico{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;background:#F3F5F4;color:var(--k2);font-size:18px;position:relative;flex:none;transition:all .35s}
.ttl{font-weight:650;font-size:13.5px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub{font-size:11px;color:var(--k3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pill{position:absolute;bottom:7px;right:9px;font-size:9.5px;font-weight:650;letter-spacing:.03em;border-radius:999px;padding:2px 7px;border:1px solid var(--line);color:var(--k3);white-space:nowrap;background:#fff}
.msg{font-size:11px;color:var(--k2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:4px;min-height:14px;padding-right:62px}
.stats{font-size:10.5px;color:var(--k3);min-height:15px;padding-right:66px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.node.running{border-color:var(--k);box-shadow:0 0 0 4px rgba(11,107,58,.10);animation:halo 1.4s ease-in-out infinite}
.node.running .ico{background:var(--k);color:#fff} .node.running .ico::after{content:"";position:absolute;inset:-4px;border-radius:12px;border:2px solid transparent;border-top-color:var(--g);animation:spin .9s linear infinite}
.node.running .pill{border-color:var(--k);color:var(--k)}
.node.done{border-color:var(--g);background:var(--gt)} .node.done .ico{background:var(--g);color:#fff} .node.done .pill{border-color:var(--g);color:var(--g);background:#fff}
.node.done .ico{animation:pop .45s ease}
.node.await{border-color:var(--g);border-style:dashed;animation:await 1.6s ease-in-out infinite} .node.await .pill{background:var(--g);color:#fff;border-color:var(--g)}
.node.error,.node.blocked{border-color:var(--k);background:#F4F4F4} .node.error .pill,.node.blocked .pill{background:var(--k);color:#fff}
.node.sel{outline:2px solid var(--k);outline-offset:3px}
.kindtag{font-size:10px;letter-spacing:.06em;color:var(--k3);text-transform:uppercase;position:absolute;left:14px;font-weight:600}
.lower{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);gap:14px;margin-top:12px}
.card{border:1px solid var(--line);border-radius:14px;background:#fff;overflow:hidden}
.card h4{margin:0;font-size:13px;font-weight:650;padding:10px 14px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px}
.card h4 span{margin-left:auto;font-weight:500;color:var(--k3);font-size:11.5px}
.log{height:300px;overflow-y:auto;font-family:"JetBrains Mono",ui-monospace,Menlo,monospace;font-size:11.5px}
.row{display:grid;grid-template-columns:88px 54px 128px 62px minmax(0,1fr);gap:8px;padding:6px 14px;border-bottom:1px solid #F0F2F1;animation:slide .35s ease}
.row .t{color:var(--k3)} .row .el{color:var(--k3);text-align:right} .row .ag{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tag{font-size:10px;border-radius:5px;padding:1px 6px;text-align:center;height:17px;border:1px solid var(--line);color:var(--k2)}
.tag.send,.tag.done,.tag.decision{background:var(--g);color:#fff;border-color:var(--g)} .tag.check{border-color:var(--g);color:var(--g)}
.tag.think,.tag.tool{background:#F3F5F4} .tag.error{background:var(--k);color:#fff} .tag.wait{border-color:var(--g);color:var(--g);border-style:dashed}
.det{height:300px;overflow-y:auto;padding:10px 14px;font-size:12.5px;line-height:1.5}
.det .l{padding:3px 0;border-bottom:1px dashed #EEF1EF;color:var(--k2)} .det .l:first-child{color:var(--k);font-weight:550}
.det .ev{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--k3);padding:2px 0}
.empty{color:var(--k3);font-size:12.5px;padding:14px}
@keyframes flow{to{stroke-dashoffset:-32}} @keyframes spin{to{transform:rotate(360deg)}} @keyframes blink{50%{opacity:.25}}
@keyframes halo{0%,100%{box-shadow:0 0 0 3px rgba(11,107,58,.08)}50%{box-shadow:0 0 0 9px rgba(11,107,58,.16)}}
@keyframes await{0%,100%{box-shadow:0 0 0 0 rgba(11,107,58,.0)}50%{box-shadow:0 0 0 8px rgba(11,107,58,.15)}}
@keyframes pop{0%{transform:scale(.6)}70%{transform:scale(1.12)}100%{transform:scale(1)}}
@keyframes slide{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style>
<div class="top">
  <span class="chip" id="cRun"></span><span class="chip" id="cBatch"></span><span class="chip" id="cClock"></span>
  <span class="chip" id="cCost"></span><span class="chip" id="cState"></span>
  <div class="ctl"><button class="btn" id="bPause">Pause</button><button class="btn sp" data-s="1">1×</button>
  <button class="btn sp on" data-s="2">2×</button><button class="btn sp" data-s="4">4×</button><button class="btn dark" id="bReplay">↺ Replay</button></div>
</div>
<div class="prog"><i id="prog"></i></div>
<div class="canvas" id="canvas">
  <span class="kindtag" style="top:8px">Intake and model</span><span class="kindtag" style="top:35.5%">Agents</span><span class="kindtag" style="top:69.5%">Decision</span>
  <svg class="edges" viewBox="0 0 1120 530" preserveAspectRatio="none" id="svg"></svg>
</div>
<div class="lower">
  <div class="card"><h4><i class="ti ti-list-details"></i>Event log<span id="evCount">0 events</span></h4><div class="log" id="log"></div></div>
  <div class="card"><h4><i class="ti ti-info-circle"></i><span style="margin:0;color:var(--k);font-size:13px;font-weight:650" id="detTitle">Step details</span><span id="detState"></span></h4><div class="det" id="det"><div class="empty">Click any step in the diagram to see what it received and sent.</div></div></div>
</div>
<script>
const D=__DATA__, W=1120, H=530, NW=214, NH=92;
const byId={}, nodeEl={}, edgeEl={}, stat={};
const canvas=document.getElementById('canvas'), svg=document.getElementById('svg'), logEl=document.getElementById('log');
const NS='http://www.w3.org/2000/svg';
const LABEL={waiting:'Waiting',running:'Running',done:'Done',await:'Your turn',error:'Error',blocked:'Rejected'};
let speed=2, paused=false, idx=0, timer=null, selected=null, follow=true;
const t0=Date.parse(D.events.length?D.events[0].t:D.run.started);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
D.nodes.forEach(n=>{byId[n.id]=n;stat[n.id]={tools:0,secs:0,usd:0,tokens:0};
  const el=document.createElement('div');el.className='node';el.style.left=((n.x-NW/2)/W*100)+'%';el.style.top=((n.y-NH/2)/H*100)+'%';
  el.style.width=(NW/W*100)+'%';el.style.height=(NH/H*100)+'%';
  el.innerHTML=`<div class="hd"><div class="ico"><i class="ti ti-${n.icon}"></i></div><div><div class="ttl">${esc(n.label)}</div><div class="sub">${esc(n.sub)}</div></div><span class="pill">Waiting</span></div><div class="msg"></div><div class="stats"></div>`;
  el.onclick=()=>{selected=n.id;follow=false;showDetail(n.id)};canvas.appendChild(el);nodeEl[n.id]=el;});
const defs=document.createElementNS(NS,'defs');defs.innerHTML='<marker id="arw" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="#9AA59E"/></marker><marker id="arwg" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="#0B6B3A"/></marker>';svg.appendChild(defs);
D.edges.forEach(e=>{const p=document.createElementNS(NS,'path');p.setAttribute('d',e.d);p.setAttribute('class','edge');p.setAttribute('marker-end','url(#arw)');svg.appendChild(p);edgeEl[e.from+'>'+e.to]=p;});
function setState(id,s){const el=nodeEl[id];if(!el)return;el.classList.remove('running','done','await','error','blocked');if(s!=='waiting')el.classList.add(s);el.querySelector('.pill').textContent=LABEL[s]||s;}
function setMsg(id,m){const el=nodeEl[id];if(el)el.querySelector('.msg').textContent=m;}
function setStats(id){const s=stat[id],b=[];if(s.tools)b.push(s.tools+' tool calls');if(s.secs)b.push(s.secs.toFixed(1)+'s');if(s.usd)b.push('$'+s.usd.toFixed(4));nodeEl[id].querySelector('.stats').textContent=b.join(' · ');}
function liveEdge(from,animate){Object.keys(edgeEl).forEach(k=>{if(k.startsWith(from+'>')){const p=edgeEl[k];p.classList.add('live');p.setAttribute('marker-end','url(#arwg)');if(animate)packet(p);}});}
function packet(path){const L=path.getTotalLength(),c=document.createElementNS(NS,'circle'),r=document.createElementNS(NS,'circle');
  c.setAttribute('r',6);c.setAttribute('class','packet');r.setAttribute('r',11);r.setAttribute('class','packet-ring');svg.appendChild(r);svg.appendChild(c);
  const dur=Math.max(450,900/speed),st=performance.now();
  (function step(now){const k=Math.min(1,(now-st)/dur),e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2,pt=path.getPointAtLength(e*L);
    c.setAttribute('cx',pt.x);c.setAttribute('cy',pt.y);r.setAttribute('cx',pt.x);r.setAttribute('cy',pt.y);r.setAttribute('stroke-opacity',.35*(1-k));
    if(k<1)requestAnimationFrame(step);else{c.remove();r.remove();}})(st);}
function fmtClock(ms){const s=Math.max(0,ms/1000);return s<60?s.toFixed(1)+'s':Math.floor(s/60)+'m '+Math.round(s%60)+'s';}
function addLog(e,animate){const row=document.createElement('div');row.className='row';if(!animate)row.style.animation='none';
  const ms=Date.parse(e.t)-t0;row.innerHTML=`<span class="t">${esc(e.t.slice(11,23))}</span><span class="el">+${fmtClock(ms)}</span><span class="ag">${esc(e.agent)}</span><span class="tag ${e.kind}">${esc(e.kind)}</span><span>${esc(e.message)}</span>`;
  logEl.appendChild(row);logEl.scrollTop=logEl.scrollHeight;document.getElementById('evCount').textContent=logEl.children.length+' events';}
function apply(e,animate){const id=e.step;
  if(['start','receive','think','tool','check'].includes(e.kind)){if(!nodeEl[id].classList.contains('done')||e.kind==='start')setState(id,'running');}
  if(e.kind==='decision'&&id==='orchestrator')setState(id,'running');
  if(e.kind==='tool'){stat[id].tools++;}
  if(e.kind==='done'){setState(id,'done');if(e.duration_s)stat[id].secs=e.duration_s;if(e.usd)stat[id].usd=e.usd;}
  if(e.kind==='send'){setState(id,'done');liveEdge(id,animate);}
  if(e.kind==='error')setState(id,'error');
  if(e.kind==='wait')setState(id,'await');
  if(e.kind==='decision'&&id==='approval'){setState(id,e.message.startsWith('Approved')?'done':'blocked');if(e.message.startsWith('Approved'))liveEdge('approval',animate);}
  setMsg(id,e.message);setStats(id);addLog(e,animate);
  document.getElementById('cClock').innerHTML='Run time <b>'+fmtClock(Date.parse(e.t)-t0)+'</b>';
  if(follow){selected=id;showDetail(id);}
  Object.values(nodeEl).forEach(n=>n.classList.remove('sel'));if(selected)nodeEl[selected].classList.add('sel');}
function showDetail(id){const n=byId[id],lines=D.summaries[id]||[];document.getElementById('detTitle').textContent=n.label;
  const st=nodeEl[id].querySelector('.pill').textContent;document.getElementById('detState').textContent=st;
  const evs=D.events.slice(0,idx).filter(e=>e.step===id).slice(-6);
  document.getElementById('det').innerHTML=lines.map(l=>`<div class="l">${esc(l)}</div>`).join('')+
   (evs.length?'<div style="margin-top:8px;font-weight:600;font-size:11.5px">Recent events</div>'+evs.map(e=>`<div class="ev">${esc(e.t.slice(11,19))} · ${esc(e.kind)} · ${esc(e.message)}</div>`).join(''):'');
  Object.values(nodeEl).forEach(x=>x.classList.remove('sel'));nodeEl[id].classList.add('sel');}
function finalize(){Object.entries(D.status).forEach(([k,v])=>{if(nodeEl[k])setState(k,v==='running'&&k==='approval'?'await':v);});
  const s=D.status.approval==='running'?'Waiting for approval':(D.status.outputs==='done'?'Completed':(D.status.approval==='blocked'?'Rejected':'Finished'));
  const st=document.getElementById('cState');st.className='chip';st.innerHTML='Status <b>'+s+'</b>';document.getElementById('prog').style.width='100%';}
function gap(i){if(i<=0)return 250;if(i>=D.events.length)return 300;const d=Date.parse(D.events[i].t)-Date.parse(D.events[i-1].t);return Math.min(1500,Math.max(160,d*0.12))/speed;}
function tick(){if(paused)return;if(idx>=D.events.length){finalize();return;}apply(D.events[idx],true);idx++;
  document.getElementById('prog').style.width=(idx/D.events.length*100)+'%';timer=setTimeout(tick,gap(idx));}
function reset(){clearTimeout(timer);idx=0;logEl.innerHTML='';follow=true;Object.keys(nodeEl).forEach(k=>{setState(k,'waiting');setMsg(k,'');stat[k]={tools:0,secs:0,usd:0,tokens:0};setStats(k);});
  Object.values(edgeEl).forEach(p=>{p.classList.remove('live');p.setAttribute('marker-end','url(#arw)');});
  const st=document.getElementById('cState');st.className='chip live';st.innerHTML='Running';}
function play(from){reset();while(idx<from&&idx<D.events.length){apply(D.events[idx],false);idx++;}timer=setTimeout(tick,300);}
document.getElementById('cRun').innerHTML='Run <b>'+esc(D.run.id)+'</b>';document.getElementById('cBatch').innerHTML='Batch <b>'+esc(D.run.batch)+'</b>';
document.getElementById('cCost').innerHTML=D.meter&&D.meter.tokens?('AI <b>'+D.meter.tokens.toLocaleString()+' tokens · $'+Number(D.meter.usd).toFixed(3)+'</b>'):'AI <b>—</b>';
document.getElementById('bReplay').onclick=()=>play(0);
document.getElementById('bPause').onclick=e=>{paused=!paused;e.target.textContent=paused?'Resume':'Pause';e.target.classList.toggle('on',paused);if(!paused)tick();};
document.querySelectorAll('.sp').forEach(b=>b.onclick=()=>{speed=+b.dataset.s;document.querySelectorAll('.sp').forEach(x=>x.classList.toggle('on',x===b));});
play(Math.min(D.start,D.events.length));
</script>
"""
