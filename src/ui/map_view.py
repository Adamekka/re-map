"""Browser floor plan for explored Mansion 1F rooms."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tracker.exploration_state import Tracker

REPO = Path(__file__).resolve().parents[2]
MAP_PROFILE_ID = "re1_directors_cut_slus00551"
logger = logging.getLogger(__name__)


def mansion_floor_plan() -> dict:
    plan = json.loads((REPO / "data/mansion1f_floor_plan.json").read_text())
    names = json.loads((REPO / "data/mansion1f_names.json").read_text())
    for room in plan["rooms"]:
        room["name"] = names.get(room["id"], "Room " + room["id"])
    return plan


def map_state(tracker: Tracker) -> dict:
    current = tracker.current
    if current is None:
        return {"status": "waiting", "current": None, "rooms": []}
    rooms = []
    if current.stage == 0:
        for region, key in sorted(tracker.region_visits.items()):
            if not region.startswith("mansion1f:"):
                continue
            record = tracker.rooms[key]
            rooms.append(
                {
                    "id": region.split(":", 1)[1],
                    "room": key,
                    "state": record.completion.value,
                    "items": [
                        {
                            "label": item.label,
                            "state": item.state,
                            "quantity": item.quantity,
                        }
                        for item in record.items
                    ],
                    "reason": record.reason,
                    "doors_complete": record.doors_complete,
                    "door_reason": record.door_reason,
                }
            )
    return {
        "status": "display",
        "current": str(current),
        "map_region": tracker.current_region.split(":", 1)[-1],
        "area": "mansion1f"
        if tracker.current_region.startswith("mansion1f:")
        else "unmapped",
        "rooms": rooms,
        "doors": [
            {
                "source": f"{door.source.room:02X}",
                "target": f"{door.target.room:02X}",
                "state": door.state,
                "label": door.label,
            }
            for door in tracker.doors
            if door.source.stage == door.target.stage == 0
        ],
    }


def map_page(graph: dict) -> bytes:
    graph_json = json.dumps(graph).replace("<", "\\u003c")
    return _PAGE.replace("__GRAPH__", graph_json).encode("utf-8")


class MapRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            body, content_type = self.server.document, "text/html; charset=utf-8"
        elif self.path == "/state":
            body, content_type = self.server.snapshot, "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/client-error":
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.send_error(400)
            return
        if length <= 0:
            self.send_error(400)
            return
        if length > 8192:
            self.send_error(413)
            return
        # Browser diagnostics are small; bound reads so a partial request cannot wait forever.
        self.connection.settimeout(2)
        try:
            error = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError, RecursionError, OSError):
            self.send_error(400)
            return
        if (
            not isinstance(error, dict)
            or set(error) != {"source", "message", "stack"}
            or not all(isinstance(value, str) for value in error.values())
        ):
            self.send_error(400)
            return
        # JSON escaping keeps arbitrary browser messages from impersonating log entries.
        logger.error("Browser error: %s", json.dumps(error))
        self.send_response(204)
        self.end_headers()

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        # Successful /state polls are frequent; retain only failed HTTP requests.
        if isinstance(code, int) and code < 400:
            return
        super().log_request(code, size)

    def log_message(self, format: str, *args: object) -> None:
        logger.warning("HTTP %s: %s", self.client_address[0], format % args)


class MapServer(ThreadingHTTPServer):
    def __init__(self, port: int, graph: dict):
        super().__init__(("127.0.0.1", port), MapRequestHandler)
        self.document = map_page(graph)
        self.snapshot = b'{"status":"waiting","current":null,"rooms":[]}'

    def handle_error(self, request: object, client_address: tuple) -> None:
        logger.exception("Map request failed for %s", client_address)


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resident Evil room map</title>
<style>
:root { color-scheme:dark; font:15px system-ui,sans-serif; background:#10151b; color:#e7edf2; }
body { margin:0; }
header { padding:22px 28px 16px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
h1 { margin:0; font-size:21px; font-weight:600; }
#place { color:#b0beca; }
#status { padding:0 28px 14px; min-height:20px; color:#abb9c5; }
main { display:grid; grid-template-columns:minmax(0,1fr) 280px; margin:0 28px; border:1px solid #303d48; background:#151e27; }
#map-shell { position:relative; min-width:0; background:radial-gradient(ellipse at center,#1c2b36,#111a22); }
svg { display:block; width:100%; height:65vh; min-height:410px; }
.room { cursor:pointer; }
.room path { stroke:#8a9ca9; stroke-width:.65; fill:#42515d; stroke-linejoin:miter; }
.room.INCOMPLETE path { fill:#743e40; }
.room.CLEARED path { fill:#244c6e; }
.room.current path { stroke:#d9f6ff; stroke-width:1.05; }
.room.selected:not(.current) path { stroke:#f0cf8c; }
.room text { fill:#dce7ee; font:2.6px system-ui,sans-serif; pointer-events:none; text-anchor:middle; }
.room.current text { font-weight:700; fill:#fff; }
.door line { stroke-width:1.1; stroke-linecap:square; }
.door.OPEN line { stroke:#71b6cf; }
.door.LOCKED line,.door.BLOCKED line { stroke:#ed6965; }
.door.UNLOCKABLE line { stroke:#e9b85e; }
.door.UNCHECKED line { stroke:#d0d9de; }
.door title { pointer-events:none; }
aside { border-left:1px solid #303d48; padding:22px; }
#room-name { font-size:18px; font-weight:600; margin:0 0 8px; }
#room-id { color:#91a5b4; font-size:13px; margin-bottom:18px; }
#completion { padding-bottom:14px; color:#ced9e1; }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:.09em; color:#91a5b4; margin:22px 0 10px; }
ul { list-style:none; margin:0; padding:0; }
li { padding:8px 0; border-top:1px solid #2d3943; display:flex; gap:10px; justify-content:space-between; font-size:13px; }
li span:last-child { color:#94a7b6; text-align:right; }
#legend { display:flex; flex-wrap:wrap; gap:12px 24px; padding:18px 28px 24px; color:#abb9c5; font-size:13px; }
.key { display:inline-block; width:13px; height:13px; margin-right:7px; vertical-align:-2px; }
.key.door-key { height:3px; vertical-align:3px; }
#note { color:#91a5b4; font-size:13px; line-height:1.5; }
@media(max-width:760px) { header { padding:18px; } #status { padding:0 18px 12px; } main { margin:0 18px; grid-template-columns:1fr; } svg { min-height:340px; height:52vh; } aside { border-left:0; border-top:1px solid #303d48; } #legend { padding:18px; } }
</style>
</head>
<body>
<header><h1>Resident Evil</h1><span id="place">Mansion · 1F</span></header>
<div id="status" role="status">Waiting for game.</div>
<main>
<div id="map-shell"><svg id="map" role="img" aria-label="Explored Mansion first floor"></svg></div>
<aside><div id="room-name">No room entered</div><div id="room-id"></div><div id="completion"></div><h2>Items</h2><ul id="items"></ul><h2>Doors</h2><ul id="doors"></ul><p id="note"></p></aside>
</main>
<div id="legend">
<span><i class="key" style="background:#743e40"></i>Items remain</span>
<span><i class="key" style="background:#244c6e"></i>Cleared</span>
<span><i class="key" style="border:2px solid #d9f6ff;box-sizing:border-box"></i>Current room</span>
<span><i class="key door-key" style="background:#ed6965"></i>Locked</span>
<span><i class="key door-key" style="background:#e9b85e"></i>Unlock from this side</span>
<span><i class="key door-key" style="background:#71b6cf"></i>Open</span>
</div>
<script>
const plan = __GRAPH__;
const byId = new Map(plan.rooms.map(room => [room.id,room]));
const svg = document.getElementById('map');
const ns = 'http://www.w3.org/2000/svg';
let selected = null;
let lastState = null;
let lastReportedError = '';
function reportError(source,error) {
  const details = {source,message:(error instanceof Error ? error.message : String(error)).slice(0,500),stack:(error instanceof Error && typeof error.stack === 'string' ? error.stack : '').slice(0,2000)};
  const key = JSON.stringify([source,details.message]);
  if(key===lastReportedError) return;
  lastReportedError=key;
  console.error('Room map error',details);
  fetch('/client-error',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(details)})
    .then(response=>{if(!response.ok){lastReportedError='';console.error('Could not record map error:',response.status);}})
    .catch(error=>{lastReportedError='';console.error('Could not record map error:',error);});
}
window.addEventListener('error',event=>reportError('window',event.error instanceof Error ? event.error : event.message));
window.addEventListener('unhandledrejection',event=>reportError('promise',event.reason));
function element(tag,attrs) {
  const node=document.createElementNS(ns,tag);
  for(const [name,value] of Object.entries(attrs)) node.setAttribute(name,value);
  return node;
}
function draw(state) {
  const status=document.getElementById('status');
  lastState=state;
  if(state.status!=='display') {
    status.textContent=state.error || 'Waiting for a readable game.';
    // Retain visit geometry; completion colors need a fresh game read after a load or reconnect.
    svg.querySelectorAll('.room').forEach(room=>{
      room.classList.remove('current','INCOMPLETE','CLEARED','VISITED');
      room.classList.add('UNKNOWN');
    });
    svg.querySelectorAll('.door').forEach(door=>door.remove());
    document.getElementById('room-id').textContent=document.getElementById('room-id').textContent.replace(' · Current room','');
    document.getElementById('completion').textContent='Tracking interrupted';
    document.getElementById('items').replaceChildren();
    document.getElementById('doors').replaceChildren();
    return;
  }
  svg.replaceChildren();
  const firstFloor=state.area==='mansion1f';
  document.getElementById('place').textContent=firstFloor?'Mansion · 1F':'Room '+state.current;
  if(!firstFloor) {
    status.textContent='Room '+state.current+'. This floor has no map yet.';
    document.getElementById('room-name').textContent='Room '+state.current;
    document.getElementById('room-id').textContent='';
    document.getElementById('completion').textContent='';
    document.getElementById('items').replaceChildren();
    document.getElementById('doors').replaceChildren();
    document.getElementById('note').textContent='';
    return;
  }
  const visible=new Map(state.rooms.filter(room=>byId.has(room.id)).map(room=>[room.id,room]));
  const currentId=(state.map_region || state.current.slice(3)).toUpperCase();
  const picked=selected && visible.has(selected) ? selected : currentId;
  status.textContent=visible.size+' '+(visible.size===1?'room':'rooms')+' explored';
  for(const [id,visit] of visible) {
    const room=byId.get(id);
    const group=element('g',{class:'room '+visit.state+(id===currentId?' current':'')+(id===picked?' selected':''),role:'button',tabindex:0,'aria-label':room.name});
    const path=room.rings.map(ring=>'M'+ring.map(point=>point.join(',')).join('L')+'Z').join('');
    group.append(element('path',{d:path,'fill-rule':'evenodd'}));
    const title=element('title',{});title.textContent=room.name;group.append(title);
    const label=element('text',{x:room.label[0],y:room.label[1]+.8});label.textContent=id;group.append(label);
    group.addEventListener('click',()=>{selected=id;draw(lastState);});
    group.addEventListener('keydown',event=>{if(event.key==='Enter' || event.key===' '){event.preventDefault();selected=id;draw(lastState);}});
    svg.append(group);
  }
  for(const marker of plan.doors) {
    if(!marker.rooms.some(id=>visible.has(id))) continue;
    // A door can be visible on an entered wall before its destination is explored.
    const observations=state.doors.filter(door=>marker.rooms.includes(door.source)&&marker.rooms.includes(door.target));
    const observed=observations.find(door=>door.source===picked)||observations.find(door=>door.source===currentId)||observations[0];
    const access=observed ? observed.state : 'UNCHECKED';
    const group=element('g',{class:'door '+access});
    const [a,b]=marker.segment;
    group.append(element('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1]}));
    const title=element('title',{});title.textContent=observed ? observed.label : 'Door';group.append(title);svg.append(group);
  }
  if(visible.size) {
    const points=[...visible.keys()].flatMap(id=>byId.get(id).rings.flat());
    const left=Math.min(...points.map(p=>p[0])),right=Math.max(...points.map(p=>p[0]));
    const top=Math.min(...points.map(p=>p[1])),bottom=Math.max(...points.map(p=>p[1]));
    const width=Math.max(68,right-left+18),height=Math.max(44,bottom-top+18);
    svg.setAttribute('viewBox',[(left+right-width)/2,(top+bottom-height)/2,width,height].join(' '));
  }
  const visit=visible.get(picked), room=byId.get(picked);
  if(!visit || !room) return;
  document.getElementById('room-name').textContent=room.name;
  document.getElementById('room-id').textContent='Room 00-'+picked+(picked===currentId?' · Current room':'');
  const completion={INCOMPLETE:'Items remain',CLEARED:'All available items collected',UNKNOWN:'Item check incomplete',VISITED:'Visited'};
  document.getElementById('completion').textContent=completion[visit.state];
  const items=document.getElementById('items');items.replaceChildren();
  for(const item of visit.items) {
    const row=document.createElement('li'), name=document.createElement('span'), detail=document.createElement('span');
    name.textContent=item.label;detail.textContent=item.state==='taken'?'Collected':item.state==='available'?'Remaining':'Not available';row.append(name,detail);items.append(row);
  }
  const doors=document.getElementById('doors');doors.replaceChildren();
  for(const door of state.doors.filter(door=>door.source===picked)) {
    const row=document.createElement('li'), name=document.createElement('span'), detail=document.createElement('span');
    name.textContent=visible.has(door.target) && byId.has(door.target)?byId.get(door.target).name:'Unexplored room';
    detail.textContent=door.label;row.append(name,detail);doors.append(row);
  }
  document.getElementById('note').textContent=[visit.reason, visit.door_reason].filter(Boolean).join(' ');
}
async function refresh() {
  try {
    const response=await fetch('/state',{cache:'no-store'});
    if(!response.ok) throw new Error('Map request failed: HTTP '+response.status);
    draw(await response.json());lastReportedError='';
  } catch(error) {
    reportError('refresh',error);
    draw({status:'waiting',error:'Map connection interrupted.'});
  }
}
refresh();setInterval(refresh,500);
</script>
</body>
</html>
"""
