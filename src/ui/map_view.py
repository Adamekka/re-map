"""Browser floor plans for explored rooms across supported game profiles."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID, uuid4

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
                {
                    "label": item.label,
                    "state": item.state,
                    "quantity": item.quantity,
                    "quantity_is_unit_count": item.quantity_is_unit_count,
                }
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
                "unlock_state": door.unlock_state.value,
                "interaction_id": door.interaction_id,
            }
            for door in tracker.doors
        ],
    }


def map_page(graph: dict, instance_id: UUID) -> bytes:
    graph_json = json.dumps(graph).replace("<", "\\u003c")
    title = (
        "Resident Evil 2" if graph["profile_id"].startswith("re2_") else "Resident Evil"
    )
    return (
        _PAGE.replace("__INSTANCE_ID__", instance_id.hex)
        .replace("__GRAPH__", graph_json)
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
        self.send_header("X-Map-Instance", self.server.instance_id.hex)
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
        # A restarted tracker can serve another profile or playthrough on the same port.
        self.instance_id = uuid4()
        self.document = map_page(graph, self.instance_id)
        self.snapshot = b'{"status":"waiting","current":null,"rooms":[]}'

    def handle_error(self, request: object, client_address: tuple) -> None:
        logger.exception("Map request failed for %s", client_address)


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="map-instance" content="__INSTANCE_ID__">
<title>__GAME_TITLE__ room map</title>
<style>
:root { color-scheme:dark; font:15px system-ui,sans-serif; background:#10151b; color:#e7edf2; }
body { margin:0; }
header { padding:22px 28px 16px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
h1 { margin:0; font-size:21px; font-weight:600; }
#place { color:#b0beca; }
#map-controls { padding:0 28px 14px; display:flex; align-items:center; flex-wrap:wrap; gap:10px; }
#zoom-controls { display:inline-flex; align-items:center; gap:10px; }
select,button,input { font:inherit; color:inherit; background:#1c2b36; border:1px solid #506473; border-radius:4px; padding:7px 10px; }
select:disabled,button:disabled,input:disabled { opacity:.55; }
#current-room[aria-pressed="true"] { border-color:#71b6cf; background:#244c6e; }
#status { padding:0 28px 14px; min-height:20px; color:#abb9c5; }
main { display:grid; grid-template-columns:minmax(0,1fr) 280px; margin:0 28px; border:1px solid #303d48; background:#151e27; }
#map-shell { position:relative; min-width:0; background:radial-gradient(ellipse at center,#1c2b36,#111a22); }
#map { display:block; width:100%; height:65vh; min-height:410px; }
#map { user-select:none; }
#map:focus-visible { outline:2px solid #d9f6ff; outline-offset:-2px; }
#map.navigable { cursor:grab; touch-action:none; }
#map.panning,#map.panning .room { cursor:grabbing; }
#zoom-level { min-width:4ch; text-align:center; font-size:13px; color:#abb9c5; }
.room { cursor:pointer; }
.room path { stroke:#8a9ca9; stroke-width:.65; fill:#42515d; stroke-linejoin:miter; }
.room.INCOMPLETE path { fill:#743e40; }
.room.INCOMPLETE.story-items > path:first-child { fill:#685331; }
.room.CLEARED path { fill:#244c6e; }
/* Unresolved rooms keep the neutral fill explicitly so a future default
cannot merge them with a decided state. */
.room.UNKNOWN path { fill:#42515d; }
.room.current path { stroke:#d9f6ff; stroke-width:1.05; }
.room.selected:not(.current) > path:first-child { stroke:#f0cf8c; }
/* Native SVG focus rings can cover nearby doors. Highlight the room wall instead. */
.room:focus-visible { outline:none; }
.room:focus-visible > path:first-child { stroke-width:1.35; }
.room:focus-visible:not(.current) > path:first-child { stroke:#a5efff; }
.room text { fill:#dce7ee; font:2.6px system-ui,sans-serif; pointer-events:none; text-anchor:middle; }
.room.current text { font-weight:700; fill:#fff; }
.room path.map-detail { fill:none; stroke:#bed0dd; stroke-width:1; stroke-linecap:square; pointer-events:none; }
.room path.map-detail-border { stroke:#8a9ca9; stroke-width:1.4; }
.room path.map-detail-core { stroke:#17232d; }
.room .map-detail+text { paint-order:stroke; stroke:#151e27; stroke-width:.5; stroke-linejoin:round; }
.player { pointer-events:none; }
.player path { fill:#a5efff; stroke:#10202b; stroke-width:.6; stroke-linejoin:round; }
.key.player-key { background:#a5efff; clip-path:polygon(50% 0,100% 100%,50% 75%,0 100%); }
.door line { stroke-width:1.4; stroke-linecap:square; }
.door.OPEN line { stroke:#71b6cf; }
.door.LOCKED line,.door.BLOCKED line { stroke:#ed6965; }
.door.UNLOCKABLE line { stroke:#e9b85e; }
.door.UNCHECKED line { stroke:#d0d9de; }
.door.UNCHECKED.unlocked line:not(.door-border) { stroke:#a5d5ac; stroke-dasharray:1.5 1; }
/* RE2 doors sit directly on walls, so a dark border keeps access colors
distinct from room outlines and fills. */
.door line.door-border { stroke:#10151b; stroke-width:2.6; }
.door title { pointer-events:none; }
.key-symbol { pointer-events:all; }
.key-symbol rect { fill:#14202a; stroke-width:.4; }
.key-symbol path { fill:none; stroke:#f3e7cd; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
.door.OPEN .key-symbol rect { stroke:#71b6cf; }
.door.LOCKED .key-symbol rect,.door.BLOCKED .key-symbol rect { stroke:#ed6965; }
.door.UNLOCKABLE .key-symbol rect { stroke:#e9b85e; }
.unlock-symbol { pointer-events:all; }
.unlock-symbol rect { fill:#14202a; stroke:#a5d5ac; stroke-width:.4; }
.unlock-symbol path { fill:none; stroke:#a5d5ac; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }
/* The badge covers the door bar, so its frame must retain access status. */
.door.UNCHECKED .unlock-symbol rect { stroke-dasharray:.9 .6; }
.door.BLOCKED .unlock-symbol rect { stroke:#ed6965; }
.door.OPEN .unlock-symbol rect { stroke:#71b6cf; }
aside { border-left:1px solid #303d48; padding:22px; }
#room-name { font-size:18px; font-weight:600; margin:0 0 8px; }
#room-id { color:#91a5b4; font-size:13px; margin-bottom:18px; }
#completion { padding-bottom:14px; color:#ced9e1; }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:.09em; color:#91a5b4; margin:22px 0 10px; }
ul { list-style:none; margin:0; padding:0; }
li { padding:8px 0; border-top:1px solid #2d3943; display:flex; gap:10px; justify-content:space-between; font-size:13px; }
li > span:last-child { color:#94a7b6; text-align:right; }
.entry-name,.entry-status { display:flex; align-items:center; gap:8px; min-width:0; }
.entry-status { justify-content:flex-end; max-width:48%; flex-shrink:0; }
.door-room-link { padding:0; border:0; background:none; text-align:left; cursor:pointer; text-decoration:underline; text-underline-offset:3px; }
.door-room-link:hover,.door-room-link:focus-visible { color:#a5efff; }
.list-symbol { display:block; flex:none; width:18px; height:18px; overflow:visible; fill:none; stroke:currentColor; stroke-width:1.3; stroke-linecap:round; stroke-linejoin:round; }
.entry-name.story,.list-symbol.story { color:#e9be72; }
.entry-name.supplies,.list-symbol.supplies { color:#df9793; }
.list-symbol.neutral { color:#94a7b6; }
.list-symbol.collected,.list-symbol.open { color:#71b6cf; }
.list-symbol.locked,.list-symbol.blocked { color:#ed6965; }
.list-symbol.unlockable { color:#e9b85e; }
.list-symbol.unlocked { color:#a5d5ac; }
#legend { display:flex; flex-wrap:wrap; gap:12px 24px; padding:18px 28px 24px; color:#abb9c5; font-size:13px; }
.key { display:inline-block; width:13px; height:13px; margin-right:7px; vertical-align:-2px; }
.key.door-key { height:3px; vertical-align:3px; }
.key.unlocked-key { height:0; border-top:3px dashed #a5d5ac; }
#note { color:#91a5b4; font-size:13px; line-height:1.5; }
#overview { display:grid; grid-template-columns:1fr 1fr; gap:28px; margin:0 28px 28px; }
#item-search-label { grid-column:1/-1; display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; font-size:13px; color:#abb9c5; }
#item-search { box-sizing:border-box; width:min(100%,320px); }
#cleared-section { grid-column:1/-1; }
#overview h2 { margin:0 0 12px; }
#overview h3 { margin:18px 0 8px; font-size:14px; font-weight:500; }
#overview p { margin:0; font-size:13px; color:#91a5b4; }
#overview li { padding:0; border:0; margin-bottom:6px; }
.room-link { display:block; width:100%; text-align:left; cursor:pointer; }
.room-link:hover,.room-link:focus-visible { border-color:#d9f6ff; }
#overview .room-link span { display:block; text-align:left; color:inherit; }
#overview .room-link span+span { margin-top:4px; color:#94a7b6; }
@media(max-width:760px) { header { padding:18px; } #map-controls { padding:0 18px 12px; } #status { padding:0 18px 12px; } main { margin:0 18px; grid-template-columns:1fr; } #map { min-height:340px; height:52vh; } aside { border-left:0; border-top:1px solid #303d48; } #legend { padding:18px; } #overview { margin:0 18px 18px; grid-template-columns:1fr; gap:22px; } }
</style>
</head>
<body>
<header><h1>__GAME_TITLE__</h1><span id="place"></span></header>
<nav id="map-controls" aria-label="Map controls"><button id="back-room" type="button" aria-label="Back to previous room" disabled>Back</button><label for="floor">Floor</label><select id="floor" disabled></select><button id="current-room" type="button" aria-pressed="false" disabled>Follow player</button><span id="zoom-controls" role="group" aria-label="Map zoom"><button id="zoom-out" type="button" aria-label="Zoom out" disabled>−</button><output id="zoom-level" aria-label="Zoom level"></output><button id="zoom-in" type="button" aria-label="Zoom in" disabled>+</button></span><button id="fit-rooms" type="button" disabled>Fit explored rooms</button></nav>
<div id="status" role="status">Waiting for game.</div>
<main>
<div id="map-shell"><svg id="map" role="group" tabindex="-1" aria-label="Explored rooms" aria-description="Arrow keys move the map. Plus and minus zoom. Zero fits explored rooms. You can also drag or use the mouse wheel."></svg></div>
<aside><div id="room-name" tabindex="-1">No room entered</div><div id="room-id"></div><div id="completion"></div><h2>Items</h2><ul id="items"></ul><h2>Doors</h2><ul id="doors"></ul><p id="note"></p></aside>
</main>
<div id="legend">
<span><i class="key" style="background:#685331"></i>Story / key items remain</span>
<span><i class="key" style="background:#743e40"></i>Supplies / other items remain</span>
<span><i class="key" style="background:#244c6e"></i>Cleared</span>
<span><i class="key" style="background:#42515d"></i>Check incomplete</span>
<span><i class="key" style="border:2px solid #d9f6ff;box-sizing:border-box"></i>Current room</span>
<span><i class="key player-key"></i><span id="player-label">You</span></span>
<span><i class="key door-key" style="background:#ed6965"></i>Locked</span>
<span><i class="key door-key" style="background:#e9b85e"></i>Unlock from this side</span>
<span><i class="key door-key" style="background:#71b6cf"></i>Open</span>
<span><i class="key door-key unlocked-key"></i>Unlocked · access unconfirmed</span>
</div>
<section id="overview" aria-label="Explored room items">
<label id="item-search-label" for="item-search">Find item or room<input id="item-search" type="search" autocomplete="off" aria-controls="remaining-items incomplete-checks cleared-rooms" disabled></label>
<section id="cleared-section" aria-labelledby="cleared-heading" hidden><h2 id="cleared-heading">Cleared rooms</h2><div id="cleared-rooms"></div></section>
<section id="remaining-section" aria-labelledby="remaining-heading"><h2 id="remaining-heading">Remaining items</h2><p id="remaining-status">Waiting for game.</p><div id="remaining-items"></div></section>
<section id="checks-section" aria-labelledby="checks-heading"><h2 id="checks-heading">Incomplete item checks</h2><p id="checks-status">Waiting for game.</p><div id="incomplete-checks"></div></section>
</section>
<script>
const catalog = __GRAPH__;
const instanceMeta = document.querySelector('meta[name="map-instance"]');
if(instanceMeta===null) throw new Error('Map page instance metadata is missing');
const mapInstance = instanceMeta.content;
const isRe2 = catalog.profile_id.startsWith('re2_');
const areas = new Map(catalog.areas.map(plan => [plan.id,plan]));
const knownRooms = new Map(catalog.areas.flatMap(plan=>[...plan.rooms,...plan.unoutlined_rooms].flatMap(region=>region.room_ids.map(id=>[id,region.name]))));
const svg = document.getElementById('map');
const ns = 'http://www.w3.org/2000/svg';
let selected = null;
let selectedArea = null;
let floorView = {mode:'follow'};
let viewHistory = [];
let lastState = null;
let lastReportedError = '';
let overviewKey = '';
const labelLayouts = new Map();
let viewport = {mode:'empty'};
let pan = {mode:'idle'};
let suppressMapClick = false;
const backRoomButton = document.getElementById('back-room');
const floorSelect = document.getElementById('floor');
const itemSearch = document.getElementById('item-search');
const currentRoomButton = document.getElementById('current-room');
const zoomIn = document.getElementById('zoom-in');
const zoomOut = document.getElementById('zoom-out');
const fitRooms = document.getElementById('fit-rooms');
itemSearch.addEventListener('input',()=>{if(lastState!==null && lastState.status==='display') updateOverview(lastState);});
itemSearch.addEventListener('keydown',event=>{
  if(event.key==='Escape' && itemSearch.value!=='') {
    event.preventDefault();
    itemSearch.value='';
    // Keyboard clearing follows the same update path as typing or the native clear control.
    itemSearch.dispatchEvent(new Event('input'));
  }
});
floorSelect.addEventListener('change',()=>{
  rememberView();
  floorView={mode:'browse',area:floorSelect.value};
  selected=null;
  draw(lastState);
});
currentRoomButton.addEventListener('click',()=>{
  viewHistory=[];
  floorView={mode:'follow'};
  selected=null;
  endPan();
  // Refit the current floor so a zoomed or panned view cannot hide our return.
  viewport={mode:'empty'};
  draw(lastState);
});
function rememberView() {
  // Interrupted maps retain room outlines, but those clicks cannot add a readable view to history.
  if(lastState===null || lastState.status!=='display') return;
  if(selectedArea===null) throw new Error('Cannot record an uninitialized map view');
  const room=svg.querySelector('.room.selected');
  if(!room && selectedArea!==lastState.area) throw new Error('Only the current room can have an unoutlined view');
  const view=room ? {kind:'outline',area:selectedArea,id:room.dataset.region} : {kind:'details',area:selectedArea,id:lastState.map_region,room:lastState.current};
  // Snapshots retain display choices so Back can render fresh game-derived state.
  viewHistory.push({...view,viewport:structuredClone(viewport)});
}
backRoomButton.addEventListener('click',()=>{
  if(lastState===null || lastState.status!=='display' || viewHistory.length===0) throw new Error('Back requires readable inspection history');
  const previous=viewHistory.pop();
  endPan();
  floorView={mode:'browse',area:previous.area};
  selectedArea=previous.area;selected=previous.id;viewport=previous.viewport;
  draw(lastState);
  focusInspectedRoom();
});
function applyViewport() {
  const ready=lastState!==null && lastState.status==='display';
  const navigable=ready && viewport.mode!=='empty';
  if(ready) {
    const room=svg.querySelector('.room.selected'),id=room ? room.dataset.region : lastState.map_region;
    // Reselecting the displayed view should not add a Back step.
    while(viewHistory.length && viewHistory.at(-1).area===selectedArea && viewHistory.at(-1).id===id) viewHistory.pop();
  }
  // Disabling a focused control would otherwise drop keyboard focus onto the page.
  const focusedBack=document.activeElement===backRoomButton;
  backRoomButton.disabled=!ready || viewHistory.length===0;
  if(focusedBack && backRoomButton.disabled) document.getElementById('room-name').focus({preventScroll:true});
  const following=ready && floorView.mode==='follow' && selected===null;
  currentRoomButton.setAttribute('aria-pressed',String(following));
  currentRoomButton.disabled=!ready || following && viewport.mode!=='manual';
  zoomIn.disabled=!navigable || viewport.zoom>=8;
  zoomOut.disabled=!navigable || viewport.zoom<=1;
  fitRooms.disabled=!navigable;
  svg.setAttribute('tabindex',navigable ? '0' : '-1');
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
svg.addEventListener('keydown',event=>{
  if(event.ctrlKey || event.metaKey || event.altKey || lastState===null || lastState.status!=='display' || viewport.mode==='empty') return;
  const button=event.key==='+' || event.key==='=' ? zoomIn : event.key==='-' ? zoomOut : event.key==='0' ? fitRooms : null;
  const horizontal=event.key==='ArrowLeft' ? -1 : event.key==='ArrowRight' ? 1 : 0;
  const vertical=event.key==='ArrowUp' ? -1 : event.key==='ArrowDown' ? 1 : 0;
  if(!button && !horizontal && !vertical) return;
  event.preventDefault();
  if(button) {button.click();return;}
  endPan();
  const [x,y,width,height]=viewport.box;
  // Scale movement with the visible map so arrow keys remain useful at every zoom.
  viewport={...viewport,mode:'manual',box:[x+horizontal*width/10,y+vertical*height/10,width,height]};
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
function itemRemains(item) {
  return item.state==='available' || item.state==='uncollected';
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
const genericKeyPath='M7 5a3 3 0 1 1-6 0a3 3 0 1 1 6 0ZM7 5h8m-3 0v3m3-3v3';
const symbolPaths=new Map([
  ...keySymbols,
  ['key',genericKeyPath],
  ['collectible','M2 4L8 1L14 4V12L8 15L2 12ZM2 4L8 7L14 4M8 7V15'],
  ['ammo','M2 14V5L4 1L6 5V14ZM10 14V5L12 1L14 5V14ZM2 11H6M10 11H14'],
  ['weapon','M1 4H14V8H9L8 14H4L5 8H1ZM9 8V10H11V8M3 4V8'],
  ['herb','M8 15V4M8 8C3 8 1 5 2 2C6 2 8 4 8 8ZM8 11C8 6 11 4 15 5C15 9 12 12 8 11Z'],
  ['spray','M5 5H12V15H3V7ZM5 5V2H11V5M11 2H15M5 10H10M7.5 7.5V12.5'],
  ['ribbon','M1 3H6V10H1ZM10 3H15V10H10ZM6 5H10M6 8H10M3 10V14H13V10'],
  ['tool','M8 1A6 6 0 1 1 8 13A6 6 0 1 1 8 1ZM8 1V13M2 7H14M8 13V15'],
  ['puzzle','M1 6H5C3 1 10 1 8 6H14V10C9 8 9 15 14 13V15H1Z'],
  ['remaining','M8 1A7 7 0 1 1 8 15A7 7 0 1 1 8 1ZM8 4V12M4 8H12'],
  ['collected','M2 8L6 12L14 3'],
  ['unresolved','M8 1A7 7 0 1 1 8 15A7 7 0 1 1 8 1ZM5.5 5A2.5 2.5 0 1 1 9 7.3L8 8V10M8 12V12.2'],
  ['inactive','M8 1A7 7 0 1 1 8 15A7 7 0 1 1 8 1ZM4 8H12'],
  ['unavailable','M8 1A7 7 0 1 1 8 15A7 7 0 1 1 8 1ZM3 3L13 13'],
  ['door','M2 15V1H13V15M5 15V4L11 2V15ZM8 9V10'],
  ['open','M2 15V1H10V5M2 15H10V12M6 8H15M12 5L15 8L12 11'],
  ['locked','M3 7H13V15H3ZM5 7V4A3 3 0 0 1 11 4V7M8 10V12'],
  ['unlockable','M3 7H13V15H3ZM5 7V4A3 3 0 0 1 11 4M8 10V12'],
  ['unlocked','M3 7H13V15H3ZM5 7V3A3 3 0 0 1 11 3M8 10V12'],
  ['blocked','M8 1A7 7 0 1 1 8 15A7 7 0 1 1 8 1ZM3 3L13 13'],
]);
const itemVisuals=new Map([
  ['supplies','ammo',['Handgun ammo','Shotgun shells','Magnum rounds','Magnum Rounds','Dum Dum Rounds','Fuel Tank','Flame Thrower Fuel','Explosive Rounds','Flame Rounds','Acid Rounds','SMGAmmo','Sparkshot Ammo','Bowgun Ammo']],
  ['supplies','weapon',['Knife','Combat Knife','Handgun','Custom Handgun','Magnum','Custom Magnum','Shotgun','Custom Shotgun','Grenade Launcher Explosive','Grenade Launcher Flame','Grenade Launcher Acid','Bowgun','Colt SAA','Sparkshot','SMG','Flamethrower','Flame Thrower','Rocket Launcher','Gatling Gun','Beretta','Handgun Parts','Magnum Parts','Shotgun Parts','Dum Dum Colt','Colt Python','Bazooka Acid','Bazooka Explosive','Bazooka Flame']],
  ['supplies','herb',['Green Herb','Red Herb','Blue Herb','Mixed Herbs']],
  ['supplies','spray',['First Aid Spray']],
  ['supplies','ribbon',['Ink Ribbon']],
  ['story','key',['Small Key','Lockpick','Lock Pick','Weapon Box Key','Special Key','Cabin Key','Down Key','Up Key','Power Room Key','Master Key','Platform Key','Control Room Key','Dorm Key 002','Dorm Key 003','Blue Card Key','Umbrella Key Card']],
  ['story','tool',['Valve Handle','Crank','Square Crank','Hex Crank','Lighter','Manhole Opener']],
  ['story','puzzle',['Serum','Antivirus Bomb','Chemical ACw32','Photo Sherry','Red Jewel','Red Card','Serpent Stone','Jaguar Stone','Jaguar Stone L','Jaguar Stone R','Eagle Stone','Bishop Plug','Rook Plug','Knight Plug','King Plug','Detonator','C4Explosive','C4Detonator','Film A','Film B','Film C','Film D','Unicorn Medal','Eagle Medal','Wolf Medal','Cog','Main Fuse','Fuse Case','Vaccine','Vaccine Cart','Vaccine Base','GVirus','Joint Plug Blue','Joint Plug Red','Cord','Photo Ada','MO Disk','Empty Bottle','Water','Umb No2','Umb No4','Umb No7','Umb No13','Yellow6','NP003','VJolt','Broken Shotgun','Wood Emblem','Gold Emblem','Blue Jewel','Music Notes','Chemical','Battery','MODisk','Wind Crest','Flare','Slides','Moon Crest','Star Crest','Sun Crest','Can Of Oil','Red Book','Doom Book2','Doom Book1','Radio']],
].flatMap(([category,symbol,labels])=>labels.map(label=>[label,{category,symbol}])));
for(const label of keySymbols.keys()) itemVisuals.set(label,{category:'story',symbol:label});
function itemVisual(label) {
  // An unresolved identity cannot establish whether an item advances the
  // story. Keep it neutral instead of classifying every unknown as a key item.
  return itemVisuals.get(label) || {category:'neutral',symbol:'collectible'};
}
function itemLabel(item) {
  // Omit the usual single unit and never turn an unresolved amount into a count.
  // Native amounts can encode weapon resources or key uses rather than object counts.
  return !item.quantity_is_unit_count || item.quantity===1 || item.quantity==='unreconstructed' ? item.label : item.label+' ×'+item.quantity;
}
function listSymbol(symbol,color) {
  if(!symbolPaths.has(symbol)) throw new Error('Unknown list symbol: '+symbol);
  const icon=element('svg',{class:'list-symbol '+color,viewBox:'0 0 16 16','aria-hidden':'true',focusable:'false'});
  icon.append(element('path',{d:symbolPaths.get(symbol)}));
  return icon;
}
function keySymbol(label) {
  const group=element('g',{class:'key-symbol',role:'img','aria-label':label});
  group.append(element('rect',{x:-2,y:-2,width:4,height:4,rx:.5}));
  // Other named keys share a key silhouette; their exact names remain in the
  // tooltip and door list instead of assigning them a Mansion emblem.
  const path=keySymbols.has(label) ? keySymbols.get(label) : genericKeyPath;
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
  const focusedRoom=svg.querySelector('.room:focus');
  const focusedDoor=document.querySelector('#doors .door-room-link:focus');
  const focusedArea=viewport.mode==='empty' ? null : viewport.area;
  lastState=state;
  if(state.status!=='display') {
    floorSelect.disabled=true;
    itemSearch.disabled=true;
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
    for(const id of ['remaining-items','incomplete-checks','cleared-rooms']) {
      const container=document.getElementById(id);
      container.replaceChildren();
      delete container.dataset.entriesKey;
    }
    document.getElementById('cleared-section').hidden=true;
    for(const id of ['remaining-section','checks-section']) document.getElementById(id).hidden=false;
    for(const id of ['remaining-status','checks-status']) {
      const message=document.getElementById(id);
      message.hidden=false;
      message.textContent='Tracking interrupted.';
    }
    if(focusedDoor) document.getElementById('room-name').focus({preventScroll:true});
    return;
  }
  const availableViews=new Map(Object.entries(state.explored_areas).map(([area,visits])=>[area,new Set(visits.map(visit=>visit.id))]));
  viewHistory=viewHistory.filter(entry=>{
    if(entry.kind==='outline') return availableViews.has(entry.area) && availableViews.get(entry.area).has(entry.id);
    // Distinct unmapped rooms can share a region ID; details are valid only for that same current room.
    if(entry.kind==='details') return entry.area===state.area && entry.id===state.map_region && entry.room===state.current;
    throw new Error('Unknown inspection history view kind');
  });
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
      floorSelect.append(option);
    }
  }
  for(const option of floorSelect.options) {
    const name=areas.has(option.value) ? areas.get(option.value).name : 'Room '+state.current;
    // Unmapped rooms share a floor ID, so their label can change without replacing the focused option.
    if(option.textContent!==name) option.textContent=name;
  }
  floorSelect.value=displayedArea;
  floorSelect.disabled=false;
  itemSearch.disabled=false;
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
    const storyItems=visit.items.some(item=>itemRemains(item) && itemVisual(item.label).category==='story');
    const group=element('g',{class:'room '+visit.state+(storyItems?' story-items':'')+(id===currentId?' current':'')+(id===picked?' selected':''),role:'button',tabindex:0,'aria-label':room.name,'data-region':id});
    const path=room.rings.map(ring=>'M'+ring.map(point=>point.join(',')).join('L')+'Z').join('');
    group.append(element('path',{d:path,'fill-rule':'evenodd'}));
    const title=element('title',{});title.textContent=room.name;group.append(title);
    const detail=room.detail_segments.map(([a,b])=>'M'+a.join(',')+'L'+b.join(',')).join('');
    if(detail) {
      // Paint all borders before all cores so adjacent native strokes form
      // one outlined structure without pale seams between its source cells.
      if(isRe2) group.append(element('path',{class:'map-detail map-detail-border',d:detail}));
      group.append(element('path',{class:'map-detail'+(isRe2 ? ' map-detail-core' : ''),d:detail}));
    }
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
      const interior=[...group.querySelectorAll('.map-detail-core')];
      const points=room.rings.flat().concat(isRe2 ? room.detail_segments.flat() : []);
      const xs=[...new Set(points.map(point=>point[0]))].sort((a,b)=>a-b);
      const ys=[...new Set(points.map(point=>point[1]))].sort((a,b)=>a-b);
      const centers=[];
      // The original anchor fits a short ID, but may sit beside a door notch.
      // Interior endpoints also expose space beside partitions when the
      // outer corners alone offer no unobstructed label position.
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
                  const point=new DOMPoint(center[0]-width/2+x*width/columns,center[1]-height/2+y*height/rows);
                  if(!outline.isPointInFill(point) || interior.some(path=>path.isPointInStroke(point))) {fits=false;break;}
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
    group.addEventListener('click',()=>{rememberView();selected=id;draw(lastState);});
    group.addEventListener('keydown',event=>{
      if(event.key==='Enter' || event.key===' ') {
        event.preventDefault();rememberView();selected=id;draw(lastState);
      }
    });
  }
  const doorGroups=[];
  for(const marker of plan ? plan.doors : []) {
    if(!marker.rooms.some(id=>visible.has(id))) continue;
    // A door can be visible on an entered wall before its destination is explored.
    const owner=byId.get(marker.rooms[0]),neighbor=byId.get(marker.rooms[1]);
    // Boundary markers encode no destination. Even a unique off-plan exit cannot
    // prove its wall identity; retain its known access in the door list instead.
    const ownerIds=owner.room_ids.map(mapRoomId),neighborIds=neighbor ? neighbor.room_ids.map(mapRoomId) : [];
    const observations=isRe2 ? state.doors.filter(door=>marker.observation_ids.includes(door.observation_id)) : neighbor ? state.doors.filter(door=>
      ownerIds.includes(mapRoomId(door.source))&&neighborIds.includes(mapRoomId(door.target)) || neighborIds.includes(mapRoomId(door.source))&&ownerIds.includes(mapRoomId(door.target))) : [];
    const pickedSource=visible.get(picked)?.room || state.current;
    const candidates=observations.filter(door=>door.source===pickedSource);
    const currentCandidates=observations.filter(door=>door.source===state.current);
    // A missing selected RE2 side cannot borrow the opposite side's lock.
    const pickedSide=isRe2 && [owner,neighbor].some(room=>room && room.room_ids.includes(pickedSource));
    const chosen=candidates.length ? candidates : pickedSide ? [] : currentCandidates.length ? currentCandidates : observations;
    // Opposite sides can agree on access while saying "No lock"/"Unlocked".
    // Resolve access and known key identity independently of that wording.
    const observed=chosen.length && chosen.every(door=>door.state===chosen[0].state) ? chosen[0] : null;
    const access=observed ? observed.state : 'UNCHECKED';
    // One bound creator supplies unlock knowledge. Agreement on access alone
    // cannot choose between opposite sides or competing creator identities.
    const unlocked=chosen.length===1 && chosen[0].unlock_state==='UNLOCKED';
    // RE2 descriptors identify the source side. RE1's paired metadata must
    // agree on key identity before either direction can display a symbol.
    const keyLabels=[...new Set((isRe2 ? chosen : observations).map(door=>door.key_label).filter(Boolean))];
    const group=element('g',{class:'door '+access+(unlocked?' unlocked':''),'data-door':marker.id,'data-observations':isRe2 ? marker.observation_ids.join(' ') : ''});
    const [a,b]=marker.segment;
    group.append(element('line',{class:'door-border',x1:a[0],y1:a[1],x2:b[0],y2:b[1]}));
    group.append(element('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1]}));
    if(unlocked) {
      const symbol=element('g',{class:'unlock-symbol',role:'img','aria-label':'Unlocked',transform:'translate('+[(a[0]+b[0])/2,(a[1]+b[1])/2].join(' ')+')'});
      symbol.append(element('rect',{x:-2,y:-2,width:4,height:4,rx:.5}));
      symbol.append(element('path',{d:symbolPaths.get('unlocked'),transform:'scale(.2) translate(-8 -8)'}));
      group.append(symbol);
    } else if(observed && access!=='OPEN' && keyLabels.length===1) {
      const symbol=keySymbol(keyLabels[0]);
      symbol.setAttribute('transform','translate('+[(a[0]+b[0])/2,(a[1]+b[1])/2].join(' ')+')');
      group.append(symbol);
    }
    const title=element('title',{});title.textContent=observed ? [...new Set(chosen.map(door=>door.label))].join(' / ') : 'Door';group.append(title);doorGroups.push(group);
  }
  // Script variants can share a doorway. Draw unresolved markers underneath
  // observed access, then keep lock symbols above other bars in the same state.
  doorGroups.sort((a,b)=>Number(!a.classList.contains('UNCHECKED'))-Number(!b.classList.contains('UNCHECKED')) || Number(Boolean(a.querySelector('.key-symbol,.unlock-symbol')))-Number(Boolean(b.querySelector('.key-symbol,.unlock-symbol')))).forEach(group=>svg.append(group));
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
  const completion={INCOMPLETE:'Items remain',CLEARED:'Cleared',UNKNOWN:'Item check incomplete',VISITED:'Visited'};
  document.getElementById('completion').textContent=completion[visit.state];
  const items=document.getElementById('items');items.replaceChildren();
  for(const item of visit.items) {
    const row=document.createElement('li'), name=document.createElement('span'), detail=document.createElement('span');
    const visual=itemVisual(item.label), status=item.state==='taken'?'collected':itemRemains(item)?'remaining':item.state==='unknown'?'unresolved':item.state==='dormant'?'inactive':'unavailable';
    name.className='entry-name '+visual.category;detail.className='entry-status';
    const label=document.createElement('span');label.textContent=itemLabel(item);name.append(listSymbol(visual.symbol,visual.category),label);
    const text=document.createElement('span');text.textContent={collected:'Collected',remaining:'Remaining',unresolved:'Unresolved',inactive:'Inactive',unavailable:'Not available'}[status];
    detail.append(listSymbol(status,status==='remaining'?visual.category:status==='collected'?'collected':'neutral'),text);row.append(name,detail);items.append(row);
  }
  const observed=observedRoomViews(state);
  const doors=document.getElementById('doors');doors.replaceChildren();
  const listedDoors=new Set();
  for(const door of state.doors.filter(door=>door.source===visit.room)) {
    if(door.interaction_id) {
      // Alternate creators share one registry slot. Collapse identical list
      // entries while retaining every source-offset observation for the map.
      const entry=JSON.stringify([door.interaction_id,door.target,door.state,door.label,door.key_label,door.unlock_state]);
      if(listedDoors.has(entry)) continue;
      listedDoors.add(entry);
    }
    const row=document.createElement('li'), name=document.createElement('span'), detail=document.createElement('span');
    name.className='entry-name';detail.className='entry-status';
    const destination=door.target_visited ? observed.get(door.target) : undefined;
    const label=document.createElement(destination ? 'button' : 'span');
    label.textContent=door.target_visited ? knownRooms.get(door.target) || 'Room '+door.target : 'Unexplored room';
    if(destination) {
      label.type='button';label.className='door-room-link';label.setAttribute('aria-label','Inspect '+label.textContent);
      label.dataset.source=door.source;label.dataset.target=door.target;label.dataset.observation=door.observation_id;
      label.addEventListener('click',()=>inspectRoom(destination.area,destination.visit.id));
    }
    name.append(listSymbol('door','neutral'),label);
    const status={OPEN:'open',LOCKED:'locked',BLOCKED:'blocked',UNLOCKABLE:'unlockable',UNCHECKED:'unresolved'}[door.state];
    if(!status) throw new Error('Unknown door state: '+door.state);
    const unlocked=door.unlock_state==='UNLOCKED';
    const symbol=door.key_label && door.state!=='OPEN' && !unlocked ? keySymbols.has(door.key_label)?door.key_label:'key' : status;
    const text=document.createElement('span');text.textContent=door.label+(!unlocked && door.key_label && !door.label.includes(door.key_label) ? ' · '+door.key_label : '');
    if(unlocked) detail.append(listSymbol('unlocked','unlocked'));
    detail.append(listSymbol(symbol,status==='unresolved'?'neutral':status),text);row.append(name,detail);doors.append(row);
  }
  document.getElementById('note').textContent=[visit.reason, visit.door_reason].filter(Boolean).join(' ');
  updateOverview(state);
  if(focusedRoom) {
    // Polls replace room nodes too. Keep the exact focused outline without changing selection or scrolling.
    const room=[...svg.querySelectorAll('.room')].find(room=>focusedArea===displayedArea && room.dataset.region===focusedRoom.dataset.region);
    if(room) room.focus({preventScroll:true});
    else svg.focus({preventScroll:true});
  } else if(focusedDoor) {
    // Door rows also redraw on live changes; keep focus on the same observed destination.
    const door=[...document.querySelectorAll('#doors .door-room-link')].find(door=>door.dataset.source===focusedDoor.dataset.source && door.dataset.target===focusedDoor.dataset.target && door.dataset.observation===focusedDoor.dataset.observation);
    if(door) door.focus({preventScroll:true});
    else document.getElementById('room-name').focus({preventScroll:true});
  }
}
function inspectRoom(area,id) {
  rememberView();
  endPan();
  floorView={mode:'browse',area};
  // A floor switch otherwise clears selection at the start of draw.
  selectedArea=area;selected=id;
  draw(lastState);
  const room=svg.querySelector('.room.selected');
  if(room) {
    const rect=room.getBoundingClientRect(),frame=svg.getBoundingClientRect();
    if(rect.left<frame.left || rect.top<frame.top || rect.right>frame.right || rect.bottom>frame.bottom) {
      const bounds=room.getBBox(),[,,width,height]=viewport.box;
      // Screen bounds account for SVG letterboxing. Preserve zoom when the room fits;
      // otherwise leave 5% margin on each side so the selection stroke stays visible.
      const ratio=rect.width<=frame.width && rect.height<=frame.height ? 1 : Math.max(rect.width/(frame.width*.9),rect.height/(frame.height*.9));
      const zoom=Math.max(1,viewport.zoom/ratio),scale=viewport.zoom/zoom;
      viewport={...viewport,mode:'manual',zoom,box:[bounds.x+bounds.width/2-width*scale/2,bounds.y+bounds.height/2-height*scale/2,width*scale,height*scale]};
      applyViewport();
    }
  }
  focusInspectedRoom();
}
function focusInspectedRoom() {
  document.querySelector('main').scrollIntoView({block:'start'});
  const room=svg.querySelector('.room.selected');
  // An unoutlined current room has details but no SVG focus target.
  const target=room || document.getElementById('room-name');
  target.focus({preventScroll:true});
}
function observedRoomViews(state) {
  // Camera outlines share a logical room's items. Prefer its current outline
  // for navigation, then retain one observed outline for each departed room.
  const observed=new Map([[state.current_detail.room,{area:state.area,visit:state.current_detail}]]);
  for(const area of Object.keys(state.explored_areas).sort()) {
    for(const visit of state.explored_areas[area]) {
      if(!observed.has(visit.room)) observed.set(visit.room,{area,visit});
    }
  }
  return observed;
}
function updateOverview(state) {
  const remaining=[],checks=[],cleared=[];
  for(const {area,visit} of observedRoomViews(state).values()) {
    if(typeof visit.items_complete!=='boolean') throw new Error('Room item coverage is missing');
    const entry={area,id:visit.id,room:visit.room,name:roomName(area,visit),labels:[]};
    if(visit.state==='CLEARED') cleared.push(entry);
    const labels=visit.items.filter(itemRemains).map(itemLabel);
    if(labels.length) remaining.push({...entry,labels});
    // A remaining item makes the room red even when other item checks are
    // incomplete. Completion color alone cannot identify those gaps.
    const unresolved=visit.items.filter(item=>item.state==='unknown').map(itemLabel);
    if(!visit.items_complete || unresolved.length) checks.push({...entry,labels:[
      ...(unresolved.length ? ['Unresolved: '+unresolved.join(', ')] : []),
      ...(!visit.items_complete ? ['Item list incomplete'] : []),
    ]});
  }
  const query=itemSearch.value.trim().toLowerCase();
  const key=JSON.stringify([query,remaining,checks,query ? cleared : []]);
  // Keep focused overview links intact during unchanged game polls.
  if(key!==overviewKey) {
    overviewKey=key;
    function showEntries(containerId,entries) {
      entries=entries.filter(entry=>{
        const floor=areas.has(entry.area) ? areas.get(entry.area).name : 'Room '+entry.room;
        return [entry.name,floor,...entry.labels].join(' ').toLowerCase().includes(query);
      }).sort((a,b)=>a.area.localeCompare(b.area)||a.name.localeCompare(b.name)||a.room.localeCompare(b.room));
      const container=document.getElementById(containerId);
      const entriesKey=JSON.stringify(entries);
      // Keep unchanged result lists intact during unrelated live updates.
      if(container.dataset.entriesKey===entriesKey) return entries.length;
      container.replaceChildren();
      const groups=new Map();
      for(const entry of entries) {
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
        link.addEventListener('click',()=>inspectRoom(entry.area,entry.id));
        row.append(link);groups.get(entry.area).append(row);
      }
      container.dataset.entriesKey=entriesKey;
      return entries.length;
    }
    // Cleared rooms are navigation results during search, while the normal overview stays focused on outstanding items.
    const clearedCount=showEntries('cleared-rooms',query ? cleared : []);
    document.getElementById('cleared-section').hidden=clearedCount===0;
    for(const [containerId,messageId,entries,emptyMessage] of [
      ['remaining-items','remaining-status',remaining,query ? 'No matching remaining items.' : 'No known remaining items.'],
      ['incomplete-checks','checks-status',checks,query ? 'No matching incomplete item checks.' : 'No incomplete item checks.'],
    ]) {
      const count=showEntries(containerId,entries),message=document.getElementById(messageId);
      message.hidden=count>0;
      message.textContent=emptyMessage;
      message.parentElement.hidden=clearedCount>0 && count===0;
    }
  }
}
let sceneKey='';
let reloading=false;
async function refresh() {
  if(reloading) return;
  const controller=new AbortController();
  let failureMessage='Map connection interrupted.';
  // A stalled response must clear live verdicts instead of leaving old game state on screen.
  const timeout=setTimeout(()=>controller.abort(new Error('Map state request timed out')),2000);
  try {
    const response=await fetch('/state',{cache:'no-store',signal:controller.signal});
    if(!response.ok) throw new Error('Map request failed: HTTP '+response.status);
    const instance=response.headers.get('X-Map-Instance');
    if(instance===null || !/^[0-9a-f]{32}$/.test(instance)) {
      controller.abort();
      failureMessage='Reload the map to reconnect to the tracker.';
      throw new Error('Map state response has no valid instance identity');
    }
    if(instance!==mapInstance) {
      reloading=true;
      controller.abort();
      endPan();
      const status=document.getElementById('status');
      status.textContent='Updating map...';
      // The next run may use another playthrough, so remove its predecessor's rooms before navigation.
      document.body.replaceChildren(status);
      window.location.reload();
      return;
    }
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
    draw({status:'waiting',error:failureMessage});
  } finally {
    clearTimeout(timeout);
    // Serial requests prevent a delayed older snapshot from replacing a newer one.
    if(!reloading) setTimeout(refresh,100);
  }
}
refresh();
</script>
</body>
</html>
"""
