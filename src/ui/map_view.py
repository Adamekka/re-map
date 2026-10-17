"""Browser floor plans for explored rooms across supported game profiles."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tracker.exploration_state import Tracker
from tracker.player_position import ApproximatePosition

MAP_PROFILE_ID = "re1_directors_cut_slus00551"
logger = logging.getLogger(__name__)


def map_state(tracker: Tracker) -> dict:
    current = tracker.current
    if current is None:
        return {"status": "waiting", "current": None, "rooms": []}
    assert tracker.player_heading is not None, (
        "a displayed player needs a coherent heading"
    )
    area = (
        tracker.current_region.split(":", 1)[0]
        if tracker.current_region
        else "unmapped"
    )

    def room_detail(key, region):
        record = tracker.rooms[key]
        return {
            "id": region,
            "room": key,
            "state": record.completion.value,
            "items_complete": record.list_complete,
            "items": [
                {"label": item.label, "state": item.state, "quantity": item.quantity}
                for item in record.items
            ],
            "reason": record.reason,
            "doors_complete": record.doors_complete,
            "door_reason": record.door_reason,
        }

    region = tracker.current_region.split(":", 1)[-1]
    # An entered elevator can put the current floor on screen before any of
    # its outlined rooms have been visited. Keep that floor selectable too.
    explored_areas = {area: []}
    for region_key, key in sorted(tracker.region_visits.items()):
        visited_area, visited_region = region_key.split(":", 1)
        explored_areas.setdefault(visited_area, []).append(
            room_detail(key, visited_region)
        )
    return {
        "status": "display",
        "current": str(current),
        "player_heading": tracker.player_heading,
        "player_position": (
            {
                "kind": "approximate",
                "point": [tracker.player_position.x, tracker.player_position.y],
            }
            if isinstance(tracker.player_position, ApproximatePosition)
            else {"kind": "room", "reason": tracker.player_position.reason}
        ),
        "map_region": region,
        "area": area,
        "map_error": tracker.map_error,
        "current_detail": room_detail(str(current), region),
        "rooms": explored_areas[area],
        "explored_areas": explored_areas,
        "doors": [
            {
                "source": str(door.source),
                "target": str(door.target),
                "target_visited": str(door.target) in tracker.rooms,
                "state": door.state,
                "label": door.label,
                "key_label": door.key_label,
                "observation_id": door.observation_id,
            }
            for door in tracker.doors
        ],
    }


def map_page(graph: dict) -> bytes:
    graph_json = json.dumps(graph).replace("<", "\\u003c")
    title = (
        "Resident Evil 2"
        if graph["profile_id"] == "re2_leon_a_slus00421"
        else "Resident Evil"
    )
    return (
        _PAGE.replace("__GRAPH__", graph_json)
        .replace("__GAME_TITLE__", title)
        .encode("utf-8")
    )


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
<title>__GAME_TITLE__ room map</title>
<style>
:root { color-scheme:dark; font:15px system-ui,sans-serif; background:#10151b; color:#e7edf2; }
body { margin:0; }
header { padding:22px 28px 16px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
h1 { margin:0; font-size:21px; font-weight:600; }
#place { color:#b0beca; }
#map-controls { padding:0 28px 14px; display:flex; align-items:center; flex-wrap:wrap; gap:10px; }
#zoom-controls { display:inline-flex; align-items:center; gap:10px; }
select,button { font:inherit; color:inherit; background:#1c2b36; border:1px solid #506473; border-radius:4px; padding:7px 10px; }
select:disabled,button:disabled { opacity:.55; }
#current-room[aria-pressed="true"] { border-color:#71b6cf; background:#244c6e; }
#status { padding:0 28px 14px; min-height:20px; color:#abb9c5; }
main { display:grid; grid-template-columns:minmax(0,1fr) 280px; margin:0 28px; border:1px solid #303d48; background:#151e27; }
#map-shell { position:relative; min-width:0; background:radial-gradient(ellipse at center,#1c2b36,#111a22); }
svg { display:block; width:100%; height:65vh; min-height:410px; }
#map { user-select:none; }
#map.navigable { cursor:grab; touch-action:none; }
#map.panning,#map.panning .room { cursor:grabbing; }
#zoom-level { min-width:4ch; text-align:center; font-size:13px; color:#abb9c5; }
.room { cursor:pointer; }
.room path { stroke:#8a9ca9; stroke-width:.65; fill:#42515d; stroke-linejoin:miter; }
.room.INCOMPLETE path { fill:#743e40; }
.room.CLEARED path { fill:#244c6e; }
/* Unresolved rooms keep the neutral fill explicitly so a future default
cannot merge them with a decided state. */
.room.UNKNOWN path { fill:#42515d; }
.room.current path { stroke:#d9f6ff; stroke-width:1.05; }
.room.selected:not(.current) path { stroke:#f0cf8c; }
.room text { fill:#dce7ee; font:2.6px system-ui,sans-serif; pointer-events:none; text-anchor:middle; }
.room.current text { font-weight:700; fill:#fff; }
.room path.map-detail { fill:none; stroke:#bed0dd; stroke-width:1; stroke-linecap:square; pointer-events:none; }
.room .map-detail+text { paint-order:stroke; stroke:#151e27; stroke-width:.5; stroke-linejoin:round; }
.player { pointer-events:none; }
.player path { fill:#a5efff; stroke:#10202b; stroke-width:.6; stroke-linejoin:round; }
.key.player-key { background:#a5efff; clip-path:polygon(50% 0,100% 100%,50% 75%,0 100%); }
.door line { stroke-width:1.1; stroke-linecap:square; }
.door.OPEN line { stroke:#71b6cf; }
.door.LOCKED line,.door.BLOCKED line { stroke:#ed6965; }
.door.UNLOCKABLE line { stroke:#e9b85e; }
.door.UNCHECKED line { stroke:#d0d9de; }
.door title { pointer-events:none; }
.key-symbol { pointer-events:all; }
.key-symbol rect { fill:#14202a; stroke-width:.4; }
.key-symbol path { fill:none; stroke:#f3e7cd; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
.door.OPEN .key-symbol rect { stroke:#71b6cf; }
.door.LOCKED .key-symbol rect,.door.BLOCKED .key-symbol rect { stroke:#ed6965; }
.door.UNLOCKABLE .key-symbol rect { stroke:#e9b85e; }
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
#overview { display:grid; grid-template-columns:1fr 1fr; gap:28px; margin:0 28px 28px; }
#overview h2 { margin:0 0 12px; }
#overview h3 { margin:18px 0 8px; font-size:14px; font-weight:500; }
#overview p { margin:0; font-size:13px; color:#91a5b4; }
#overview li { padding:0; border:0; margin-bottom:6px; }
.room-link { display:block; width:100%; text-align:left; cursor:pointer; }
.room-link:hover,.room-link:focus-visible { border-color:#d9f6ff; }
#overview .room-link span { display:block; text-align:left; color:inherit; }
#overview .room-link span+span { margin-top:4px; color:#94a7b6; }
@media(max-width:760px) { header { padding:18px; } #map-controls { padding:0 18px 12px; } #status { padding:0 18px 12px; } main { margin:0 18px; grid-template-columns:1fr; } svg { min-height:340px; height:52vh; } aside { border-left:0; border-top:1px solid #303d48; } #legend { padding:18px; } #overview { margin:0 18px 18px; grid-template-columns:1fr; gap:22px; } }
</style>
</head>
<body>
<header><h1>__GAME_TITLE__</h1><span id="place"></span></header>
<nav id="map-controls" aria-label="Map controls"><label for="floor">Floor</label><select id="floor" disabled></select><button id="current-room" type="button" aria-pressed="false" disabled>Follow player</button><span id="zoom-controls" role="group" aria-label="Map zoom"><button id="zoom-out" type="button" aria-label="Zoom out" disabled>−</button><output id="zoom-level" aria-label="Zoom level"></output><button id="zoom-in" type="button" aria-label="Zoom in" disabled>+</button></span><button id="fit-rooms" type="button" disabled>Fit explored rooms</button></nav>
<div id="status" role="status">Waiting for game.</div>
<main>
<div id="map-shell"><svg id="map" role="img" aria-label="Explored rooms" aria-description="Use the zoom buttons or mouse wheel to zoom. Drag to move the map."></svg></div>
<aside><div id="room-name" tabindex="-1">No room entered</div><div id="room-id"></div><div id="completion"></div><h2>Items</h2><ul id="items"></ul><h2>Doors</h2><ul id="doors"></ul><p id="note"></p></aside>
</main>
<div id="legend">
<span><i class="key" style="background:#743e40"></i>Items remain</span>
<span><i class="key" style="background:#244c6e"></i>Cleared</span>
<span><i class="key" style="background:#42515d"></i>Check incomplete</span>
<span><i class="key" style="border:2px solid #d9f6ff;box-sizing:border-box"></i>Current room</span>
<span><i class="key player-key"></i><span id="player-label">You</span></span>
<span><i class="key door-key" style="background:#ed6965"></i>Locked</span>
<span><i class="key door-key" style="background:#e9b85e"></i>Unlock from this side</span>
<span><i class="key door-key" style="background:#71b6cf"></i>Open</span>
</div>
<section id="overview" aria-label="Explored room items">
<section aria-labelledby="remaining-heading"><h2 id="remaining-heading">Remaining items</h2><p id="remaining-status">Waiting for game.</p><div id="remaining-items"></div></section>
<section aria-labelledby="checks-heading"><h2 id="checks-heading">Incomplete item checks</h2><p id="checks-status">Waiting for game.</p><div id="incomplete-checks"></div></section>
</section>
<script>
const catalog = __GRAPH__;
const areas = new Map(catalog.areas.map(plan => [plan.id,plan]));
const knownRooms = new Map(catalog.areas.flatMap(plan=>[...plan.rooms,...plan.unoutlined_rooms].flatMap(region=>region.room_ids.map(id=>[id,region.name]))));
const svg = document.getElementById('map');
const ns = 'http://www.w3.org/2000/svg';
let selected = null;
let selectedArea = null;
let floorView = {mode:'follow'};
let lastState = null;
let lastReportedError = '';
let overviewKey = '';
const labelLayouts = new Map();
let viewport = {mode:'empty'};
let pan = {mode:'idle'};
let suppressMapClick = false;
const floorSelect = document.getElementById('floor');
const currentRoomButton = document.getElementById('current-room');
const zoomIn = document.getElementById('zoom-in');
const zoomOut = document.getElementById('zoom-out');
const fitRooms = document.getElementById('fit-rooms');
floorSelect.addEventListener('change',()=>{
  floorView={mode:'browse',area:floorSelect.value};
  selected=null;
  draw(lastState);
});
currentRoomButton.addEventListener('click',()=>{
  floorView={mode:'follow'};
  selected=null;
  endPan();
  // Refit the current floor so a zoomed or panned view cannot hide our return.
  viewport={mode:'empty'};
  draw(lastState);
});
function applyViewport() {
  const ready=lastState!==null && lastState.status==='display';
  const navigable=ready && viewport.mode!=='empty';
  const following=ready && floorView.mode==='follow' && selected===null;
  currentRoomButton.setAttribute('aria-pressed',String(following));
  currentRoomButton.disabled=!ready || following && viewport.mode!=='manual';
  zoomIn.disabled=!navigable || viewport.zoom>=8;
  zoomOut.disabled=!navigable || viewport.zoom<=1;
  fitRooms.disabled=!navigable;
  document.getElementById('zoom-level').textContent=navigable ? Math.round(viewport.zoom*100)+'%' : '';
  svg.classList.toggle('navigable',navigable);
  if(viewport.mode!=='empty') {
    if(!viewport.box.every(Number.isFinite) || viewport.box[2]<=0 || viewport.box[3]<=0) throw new Error('Invalid map viewport');
    svg.setAttribute('viewBox',viewport.box.join(' '));
  }
  if(lastState && lastState.status==='display') updatePlayer();
}
function zoomMap(factor,point) {
  if(viewport.mode==='empty') throw new Error('Cannot zoom an empty map');
  // Bound wheel zoom so the view cannot collapse to a point after repeated input.
  const zoom=Math.max(1,Math.min(8,viewport.zoom/factor));
  if(zoom===viewport.zoom) return;
  const ratio=viewport.zoom/zoom,[x,y,width,height]=viewport.box;
  viewport={...viewport,mode:'manual',zoom,box:[point.x+(x-point.x)*ratio,point.y+(y-point.y)*ratio,width*ratio,height*ratio]};
  applyViewport();
}
for(const [button,factor] of [[zoomIn,.8],[zoomOut,1.25]]) {
  button.addEventListener('click',()=>{
    endPan();
    const [x,y,width,height]=viewport.box;
    zoomMap(factor,new DOMPoint(x+width/2,y+height/2));
  });
}
fitRooms.addEventListener('click',()=>{
  endPan();
  viewport={...viewport,mode:'fit',zoom:1,box:viewport.fitBox};
  applyViewport();
});
svg.addEventListener('wheel',event=>{
  // Keep browser zoom available and leave page scrolling alone without a map.
  if(event.ctrlKey || event.deltaY===0 || lastState===null || lastState.status!=='display' || viewport.mode==='empty') return;
  event.preventDefault();
  endPan();
  // Line and page wheel events need pixel-sized steps for the same zoom curve.
  const unit=event.deltaMode===1 ? 16 : event.deltaMode===2 ? svg.clientHeight : 1;
  const factor=Math.exp(Math.max(-1,Math.min(1,event.deltaY*unit/400)));
  const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());
  zoomMap(factor,point);
},{passive:false});
function endPan() {
  if(pan.mode==='idle') return;
  // Cancellation can still be followed by a browser click on the original room.
  suppressMapClick=suppressMapClick || pan.mode==='panning';
  const pointerId=pan.pointerId;
  pan={mode:'idle'};
  svg.classList.remove('panning');
  if(svg.hasPointerCapture(pointerId)) svg.releasePointerCapture(pointerId);
}
svg.addEventListener('pointerdown',event=>{
  if(event.button!==0 || !event.isPrimary || lastState===null || lastState.status!=='display' || viewport.mode==='empty') return;
  endPan();
  suppressMapClick=false;
  pan={mode:'pending',pointerId:event.pointerId,start:[event.clientX,event.clientY],matrix:svg.getScreenCTM().inverse(),box:viewport.box,zoom:viewport.zoom};
});
window.addEventListener('pointermove',event=>{
  if(pan.mode==='idle' || event.pointerId!==pan.pointerId) return;
  if(event.buttons===0) {endPan();return;}
  if(pan.mode==='pending') {
    // A small movement is still a room click; capture only an actual drag.
    if(Math.hypot(event.clientX-pan.start[0],event.clientY-pan.start[1])<4) return;
    pan={...pan,mode:'panning'};
    svg.setPointerCapture(event.pointerId);
    svg.classList.add('panning');
  }
  const start=new DOMPoint(...pan.start).matrixTransform(pan.matrix);
  const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(pan.matrix);
  const [x,y,width,height]=pan.box;
  viewport={...viewport,mode:'manual',zoom:pan.zoom,box:[x+start.x-point.x,y+start.y-point.y,width,height]};
  applyViewport();
});
window.addEventListener('pointerup',event=>{
  if(pan.mode==='idle' || event.pointerId!==pan.pointerId) return;
  suppressMapClick=pan.mode==='panning';
  endPan();
});
window.addEventListener('pointercancel',event=>{if(pan.mode!=='idle' && event.pointerId===pan.pointerId) endPan();});
svg.addEventListener('lostpointercapture',event=>{if(pan.mode!=='idle' && event.pointerId===pan.pointerId) endPan();});
window.addEventListener('blur',endPan);
svg.addEventListener('click',event=>{
  if(suppressMapClick && event.detail>0) {suppressMapClick=false;event.preventDefault();event.stopPropagation();}
},{capture:true});
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
function roomName(area,visit) {
  const plan=areas.get(area);
  const room=plan && [...plan.rooms,...plan.unoutlined_rooms].find(room=>room.id===visit.id);
  return room ? room.name : 'Room '+visit.room;
}
function mapRoomId(room) {
  // The original and returned Mansion share floor geometry, including rooms
  // whose RDT exists only in the later stage. Match the layout's stage modulus.
  const [stage,id]=room.split('-');
  return (parseInt(stage,16)%catalog.stage_modulus).toString(16).padStart(2,'0')+'-'+id;
}
const keySymbols=new Map([
  ['Spade Key','M8 1C5 5 1 6 1 10C1 14 6 14 8 11C10 14 15 14 15 10C15 6 11 5 8 1ZM8 10V15M5 15H11'],
  ['Diamond Key','M8 1L14 8L8 15L2 8Z'],
  ['Heart Key','M8 15C5 11 1 9 1 5C1 0 6 0 8 4C10 0 15 0 15 5C15 9 11 11 8 15Z'],
  ['Club Key','M8 8C3 10 0 8 1 5C2 2 5 3 6 5C3 0 11 0 11 4C11 5 10 6 9 7C13 3 17 7 14 10C12 12 9 10 8 8ZM8 8V15M5 15H11'],
  ['Sword Key','M10 2H14V6L6 14L2 10ZM5 7L11 13M5 12L2 15'],
  ['Armor Key','M5 2L8 4L11 2L15 5L12 8V14H4V8L1 5ZM5 2V5L8 7L11 5V2M4 11H12'],
  ['Shield Key','M2 2H14V7Q14 12 8 15Q2 12 2 7ZM8 3V12M4 7H12'],
  ['Helmet Key','M3 10V7A5 5 0 0 1 13 7V14H9L7 10ZM8 2V6M3 7H10M10 7V10H13'],
]);
function keySymbol(label) {
  const group=element('g',{class:'key-symbol',role:'img','aria-label':label});
  group.append(element('rect',{x:-2,y:-2,width:4,height:4,rx:.5}));
  // Other named keys share a key silhouette; their exact names remain in the
  // tooltip and door list instead of assigning them a Mansion emblem.
  const path=keySymbols.has(label) ? keySymbols.get(label) : 'M7 5a3 3 0 1 1-6 0a3 3 0 1 1 6 0ZM7 5h8m-3 0v3m3-3v3';
  group.append(element('path',{d:path,transform:'scale(.2) translate(-8 -8)'}));
  const title=element('title',{});title.textContent=label;group.append(title);
  return group;
}
function updatePlayer() {
  const group=svg.querySelector('.player');
  if(!group) return;
  const marker=group.querySelector('path');
  if(lastState.status!=='display' || !Number.isFinite(lastState.player_heading) || lastState.player_heading<0 || lastState.player_heading>=360) throw new Error('Player heading is missing or invalid');
  const position=lastState.player_position;
  if(position.kind==='approximate') {
    if(position.point.length!==2 || !position.point.every(Number.isFinite)) throw new Error('Player position is missing or invalid');
    group.setAttribute('transform','translate('+position.point.join(' ')+')');
  } else if(position.kind!=='room') throw new Error('Player position accuracy is invalid');
  // Keep the locator readable at both a whole-floor view and a close zoom.
  const matrix=svg.getScreenCTM(),scale=3.5/Math.hypot(matrix.a,matrix.b);
  // A room-only arrow sits above the wall. A position estimate is centered
  // on its projected point, so rotation cannot move it around that point.
  marker.setAttribute('transform','translate(0 '+(position.kind==='room' ? -3.6*scale : 0)+') rotate('+lastState.player_heading+') scale('+scale+')');
}
function draw(state) {
  const status=document.getElementById('status');
  lastState=state;
  if(state.status!=='display') {
    floorSelect.disabled=true;
    endPan();
    applyViewport();
    status.textContent=state.error || 'Waiting for a readable game.';
    // Retain visit geometry; completion colors need a fresh game read after a load or reconnect.
    svg.querySelectorAll('.room').forEach(room=>{
      room.classList.remove('current','INCOMPLETE','CLEARED','VISITED');
      room.classList.add('UNKNOWN');
    });
    svg.querySelectorAll('.door,.player').forEach(marker=>marker.remove());
    document.getElementById('room-id').textContent=document.getElementById('room-id').textContent.replace(' · Current room','');
    document.getElementById('completion').textContent='Tracking interrupted';
    document.getElementById('items').replaceChildren();
    document.getElementById('doors').replaceChildren();
    document.getElementById('note').textContent='';
    overviewKey='';
    document.getElementById('remaining-items').replaceChildren();
    document.getElementById('incomplete-checks').replaceChildren();
    for(const id of ['remaining-status','checks-status']) {
      const message=document.getElementById(id);
      message.hidden=false;
      message.textContent='Tracking interrupted.';
    }
    return;
  }
  if(floorView.mode==='browse' && !Object.hasOwn(state.explored_areas,floorView.area)) {
    // A new playthrough can remove the browsed floor. Resume following instead
    // of retaining geometry or verdicts from the previous exploration history.
    floorView={mode:'follow'};
    selected=null;
  }
  const displayedArea=floorView.mode==='browse' ? floorView.area : state.area;
  const showingCurrentFloor=displayedArea===state.area;
  const floorIds=Object.keys(state.explored_areas).sort();
  // Polling must not replace a focused select every half second; keep native
  // keyboard navigation intact until the explored-floor list actually changes.
  if(JSON.stringify(floorIds)!==JSON.stringify([...floorSelect.options].map(option=>option.value))) {
    floorSelect.replaceChildren();
    for(const id of floorIds) {
      const option=document.createElement('option');
      option.value=id;
      option.textContent=areas.has(id) ? areas.get(id).name : 'Room '+state.current;
      floorSelect.append(option);
    }
  }
  floorSelect.value=displayedArea;
  floorSelect.disabled=false;
  svg.replaceChildren();
  const plan=areas.get(displayedArea);
  if(selectedArea!==displayedArea) {selected=null;selectedArea=displayedArea;}
  const byId=new Map((plan ? plan.rooms : []).map(room=>[room.id,room]));
  document.getElementById('place').textContent=plan ? plan.name : 'Room '+state.current;
  svg.setAttribute('aria-label',plan ? 'Explored '+plan.name : 'Explored rooms');
  const visible=new Map(state.explored_areas[displayedArea].filter(room=>byId.has(room.id)).map(room=>[room.id,room]));
  const currentId=showingCurrentFloor ? state.map_region : null;
  const picked=selected && visible.has(selected) ? selected : showingCurrentFloor ? currentId : visible.keys().next().value;
  status.textContent=plan ? visible.size+' '+(visible.size===1?'room':'rooms')+' explored' : state.map_error;
  if(plan && showingCurrentFloor && !byId.has(currentId)) status.textContent+=' · This room has no outline on the game map.';
  document.getElementById('player-label').textContent=state.player_position.kind==='approximate' ? 'You · approximate' : 'You · room only';
  for(const [id,visit] of visible) {
    const room=byId.get(id);
    const group=element('g',{class:'room '+visit.state+(id===currentId?' current':'')+(id===picked?' selected':''),role:'button',tabindex:0,'aria-label':room.name});
    const path=room.rings.map(ring=>'M'+ring.map(point=>point.join(',')).join('L')+'Z').join('');
    group.append(element('path',{d:path,'fill-rule':'evenodd'}));
    const title=element('title',{});title.textContent=room.name;group.append(title);
    const detail=room.detail_segments.map(([a,b])=>'M'+a.join(',')+'L'+b.join(',')).join('');
    if(detail) group.append(element('path',{class:'map-detail',d:detail}));
    const label=element('text',{});group.append(label);svg.append(group);
    function setLines(lines) {
      label.replaceChildren();
      for(const [index,line] of lines.entries()) {
        const span=element('tspan',{x:0,y:(index-(lines.length-1)/2)*3.1});
        span.textContent=line;label.append(span);
      }
    }
    const labelKey=displayedArea+':'+id+':'+(id===currentId);
    let layout=labelLayouts.get(labelKey);
    if(!layout) {
      const words=room.name.split(' '),variants=[];
      for(let count=words.length;count>=1;count--) {
        const lines=[];
        for(let start=0;start<words.length;start+=count) lines.push(words.slice(start,start+count).join(' '));
        setLines(lines);
        variants.push({lines,bounds:label.getBBox()});
      }
      const outline=group.querySelector('path');
      const points=room.rings.flat();
      const xs=[...new Set(points.map(point=>point[0]))].sort((a,b)=>a-b);
      const ys=[...new Set(points.map(point=>point[1]))].sort((a,b)=>a-b);
      const centers=[];
      // The original anchor fits a short ID, but may sit beside a door notch.
      // Rectangle centers offer nearby positions inside the same room.
      for(let x=1;x<xs.length;x++) {
        for(let y=1;y<ys.length;y++) {
          const center=[(xs[x-1]+xs[x])/2,(ys[y-1]+ys[y])/2];
          if(outline.isPointInFill(new DOMPoint(...center))) centers.push(center);
        }
      }
      centers.sort((a,b)=>Math.hypot(a[0]-room.label[0],a[1]-room.label[1])-Math.hypot(b[0]-room.label[0],b[1]-room.label[1]));
      centers.unshift(room.label);
      const baseSize=parseFloat(getComputedStyle(label).fontSize);
      // Room shapes are irregular. Fit the whole name inside the entered
      // outline, turning labels along narrow passages when that fits better.
      fitting: for(let tenths=Math.round(baseSize*10);tenths>=5;tenths--) {
        for(const angle of [0,-90]) {
          for(const {lines,bounds} of variants) {
            const scale=tenths/10/baseSize;
            const width=(angle===0 ? bounds.width : bounds.height)*scale+.8;
            const height=(angle===0 ? bounds.height : bounds.width)*scale+.8;
            for(const center of centers) {
              if(![-1,1].every(x=>[-1,1].every(y=>outline.isPointInFill(new DOMPoint(center[0]+x*width/2,center[1]+y*height/2))))) continue;
              const columns=Math.ceil(width/.5),rows=Math.ceil(height/.5);
              let fits=true;
              // Native outlines use a one-unit grid; sampling every half unit
              // also catches corridor bends and interior gaps between corners.
              for(let x=0;x<=columns && fits;x++) {
                for(let y=0;y<=rows;y++) {
                  if(!outline.isPointInFill(new DOMPoint(center[0]-width/2+x*width/columns,center[1]-height/2+y*height/rows))) {fits=false;break;}
                }
              }
              if(fits) {layout={lines,angle,scale,center,offset:[-bounds.x-bounds.width/2,-bounds.y-bounds.height/2]};break fitting;}
            }
          }
        }
      }
      if(!layout) throw new Error('Room name does not fit its outline: '+room.name);
      // Geometry and names are fixed. Reuse their layout during polling;
      // current-room weight has its own entry because bold text is wider.
      labelLayouts.set(labelKey,layout);
    }
    label.setAttribute('transform','translate('+layout.center.join(' ')+') rotate('+layout.angle+') scale('+layout.scale+') translate('+layout.offset.join(' ')+')');
    setLines(layout.lines);
    group.addEventListener('click',()=>{selected=id;draw(lastState);});
    group.addEventListener('keydown',event=>{if(event.key==='Enter' || event.key===' '){event.preventDefault();selected=id;draw(lastState);}});
  }
  for(const marker of plan ? plan.doors : []) {
    if(!marker.rooms.some(id=>visible.has(id))) continue;
    // A door can be visible on an entered wall before its destination is explored.
    const owner=byId.get(marker.rooms[0]),neighbor=byId.get(marker.rooms[1]);
    // Boundary markers encode no destination. Even a unique off-plan exit cannot
    // prove its wall identity; retain its known access in the door list instead.
    const ownerIds=owner.room_ids.map(mapRoomId),neighborIds=neighbor ? neighbor.room_ids.map(mapRoomId) : [];
    const observations=marker.observation_id ? state.doors.filter(door=>door.observation_id===marker.observation_id) : neighbor ? state.doors.filter(door=>
      ownerIds.includes(mapRoomId(door.source))&&neighborIds.includes(mapRoomId(door.target)) || neighborIds.includes(mapRoomId(door.source))&&ownerIds.includes(mapRoomId(door.target))) : [];
    const pickedSource=visible.get(picked)?.room || state.current;
    const candidates=observations.filter(door=>door.source===pickedSource);
    const currentCandidates=observations.filter(door=>door.source===state.current);
    const chosen=candidates.length ? candidates : currentCandidates.length ? currentCandidates : observations;
    // Opposite sides can agree on access while saying "No lock"/"Unlocked".
    // Resolve access and known key identity independently of that wording.
    const observed=chosen.length && chosen.every(door=>door.state===chosen[0].state) ? chosen[0] : null;
    const access=observed ? observed.state : 'UNCHECKED';
    const keyLabels=[...new Set(observations.map(door=>door.key_label).filter(Boolean))];
    const group=element('g',{class:'door '+access,'data-door':marker.id});
    const [a,b]=marker.segment;
    group.append(element('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1]}));
    if(observed && access!=='OPEN' && keyLabels.length===1) {
      const symbol=keySymbol(keyLabels[0]);
      symbol.setAttribute('transform','translate('+[(a[0]+b[0])/2,(a[1]+b[1])/2].join(' ')+')');
      group.append(symbol);
    }
    const title=element('title',{});title.textContent=observed ? [...new Set(chosen.map(door=>door.label))].join(' / ') : 'Door';group.append(title);svg.append(group);
  }
  if(visible.has(currentId)) {
    const room=byId.get(currentId);
    // Games or rooms without position support retain an explicitly room-only
    // marker above the wall. Approximate coordinates update in updatePlayer.
    const top=Math.min(...room.rings.flat().map(point=>point[1]));
    const edge=room.rings.flatMap(ring=>ring.map((a,index)=>[a,ring[(index+1)%ring.length]]))
      .filter(([a,b])=>a[1]===top && b[1]===top).sort(([a,b],[c,d])=>Math.abs(d[0]-c[0])-Math.abs(b[0]-a[0]))[0];
    const approximate=state.player_position.kind==='approximate';
    const marker=element('g',{class:'player',transform:'translate('+[(edge[0][0]+edge[1][0])/2,top].join(' ')+')',role:'img','aria-label':(approximate ? 'Approximate position · ' : 'You · ')+room.name});
    marker.append(element('path',{d:'M0,-3 L2.2,2.4 L0,1.2 L-2.2,2.4 Z'}));
    const title=element('title',{});title.textContent=approximate ? 'Approximate position · '+room.name : 'Your current room · '+room.name+' · '+state.player_position.reason;marker.append(title);
    svg.append(marker);
  }
  if(visible.size) {
    const points=[...visible.keys()].flatMap(id=>byId.get(id).rings.flat());
    const left=Math.min(...points.map(p=>p[0])),right=Math.max(...points.map(p=>p[0]));
    const top=Math.min(...points.map(p=>p[1])),bottom=Math.max(...points.map(p=>p[1]));
    const width=Math.max(68,right-left+18),height=Math.max(44,bottom-top+18);
    const fitBox=[(left+right-width)/2,(top+bottom-height)/2,width,height];
    if(viewport.mode==='empty' || viewport.area!==displayedArea) {
      endPan();
      viewport={mode:'fit',area:displayedArea,zoom:1,box:fitBox,fitBox};
    } else {
      // Item changes and newly entered rooms must not reframe a chosen view.
      viewport={...viewport,fitBox,box:viewport.mode==='fit' ? fitBox : viewport.box};
    }
  } else {
    endPan();
    viewport={mode:'empty'};
  }
  applyViewport();
  const visit=showingCurrentFloor && picked===currentId ? state.current_detail : visible.get(picked);
  if(!visit) throw new Error('Explored floor has no selected room');
  document.getElementById('room-name').textContent=roomName(displayedArea,visit);
  document.getElementById('room-id').textContent='Room '+visit.room+(showingCurrentFloor && picked===currentId?' · Current room':'');
  const completion={INCOMPLETE:'Items remain',CLEARED:'All available items collected',UNKNOWN:'Item check incomplete',VISITED:'Visited'};
  document.getElementById('completion').textContent=completion[visit.state];
  const items=document.getElementById('items');items.replaceChildren();
  for(const item of visit.items) {
    const row=document.createElement('li'), name=document.createElement('span'), detail=document.createElement('span');
    name.textContent=item.label;detail.textContent=item.state==='taken'?'Collected':item.state==='available'?'Remaining':item.state==='unknown'?'Unresolved':item.state==='dormant'?'Inactive':'Not available';row.append(name,detail);items.append(row);
  }
  const doors=document.getElementById('doors');doors.replaceChildren();
  for(const door of state.doors.filter(door=>door.source===visit.room)) {
    const row=document.createElement('li'), name=document.createElement('span'), detail=document.createElement('span');
    name.textContent=door.target_visited ? knownRooms.get(door.target) || 'Room '+door.target : 'Unexplored room';
    detail.textContent=door.label+(door.key_label && !door.label.includes(door.key_label) ? ' · '+door.key_label : '');row.append(name,detail);doors.append(row);
  }
  document.getElementById('note').textContent=[visit.reason, visit.door_reason].filter(Boolean).join(' ');
  // Camera outlines share a logical room's items. Prefer its current outline
  // for navigation, then retain one observed outline for each departed room.
  const observed=new Map([[state.current_detail.room,{area:state.area,visit:state.current_detail}]]);
  for(const area of floorIds) {
    for(const visit of state.explored_areas[area]) {
      if(!observed.has(visit.room)) observed.set(visit.room,{area,visit});
    }
  }
  const remaining=[],checks=[];
  for(const {area,visit} of observed.values()) {
    if(typeof visit.items_complete!=='boolean') throw new Error('Room item coverage is missing');
    const entry={area,id:visit.id,room:visit.room,name:roomName(area,visit),labels:[]};
    const labels=visit.items.filter(item=>item.state==='available').map(item=>item.label);
    if(labels.length) remaining.push({...entry,labels});
    // A remaining item makes the room red even when other item checks are
    // incomplete. Completion color alone cannot identify those gaps.
    if(!visit.items_complete || visit.items.some(item=>item.state==='unknown')) checks.push(entry);
  }
  const key=JSON.stringify([remaining,checks]);
  // Keep focused overview links intact during unchanged game polls.
  if(key!==overviewKey) {
    overviewKey=key;
    function showEntries(containerId,messageId,entries,emptyMessage) {
      const container=document.getElementById(containerId);
      container.replaceChildren();
      const message=document.getElementById(messageId);
      message.hidden=entries.length>0;
      message.textContent=emptyMessage;
      const groups=new Map();
      for(const entry of entries.sort((a,b)=>a.area.localeCompare(b.area)||a.name.localeCompare(b.name)||a.room.localeCompare(b.room))) {
        if(!groups.has(entry.area)) {
          const heading=document.createElement('h3'),list=document.createElement('ul');
          heading.textContent=areas.has(entry.area) ? areas.get(entry.area).name : 'Room '+entry.room;
          container.append(heading,list);groups.set(entry.area,list);
        }
        const row=document.createElement('li'),link=document.createElement('button'),name=document.createElement('span');
        link.type='button';link.className='room-link';name.textContent=entry.name;link.append(name);
        if(entry.labels.length) {
          const labels=document.createElement('span');labels.textContent=entry.labels.join(', ');link.append(labels);
        }
        link.addEventListener('click',()=>{
          floorView={mode:'browse',area:entry.area};
          // A floor switch otherwise clears selection at the start of draw.
          selectedArea=entry.area;selected=entry.id;
          draw(lastState);
          document.querySelector('main').scrollIntoView({block:'start'});
          // An unoutlined current room has details but no SVG focus target.
          const target=svg.querySelector('.room.selected') || document.getElementById('room-name');
          target.focus({preventScroll:true});
        });
        row.append(link);groups.get(entry.area).append(row);
      }
    }
    showEntries('remaining-items','remaining-status',remaining,'No known remaining items.');
    showEntries('incomplete-checks','checks-status',checks,'No incomplete item checks.');
  }
}
let sceneKey='';
async function refresh() {
  try {
    const response=await fetch('/state',{cache:'no-store'});
    if(!response.ok) throw new Error('Map request failed: HTTP '+response.status);
    const state=await response.json();
    const {player_heading,player_position,...scene}=state;
    const position=state.status==='display' ? player_position : {kind:'waiting'};
    const key=JSON.stringify({...scene,player_position:position.kind==='approximate' ? 'approximate' : position});
    // Pose-only polls must preserve room click targets and the chosen view.
    if(key!==sceneKey) {draw(state);sceneKey=key;}
    else {lastState=state;updatePlayer();}
    lastReportedError='';
  } catch(error) {
    reportError('refresh',error);
    sceneKey='';
    draw({status:'waiting',error:'Map connection interrupted.'});
  }
}
refresh();setInterval(refresh,100);
</script>
</body>
</html>
"""
