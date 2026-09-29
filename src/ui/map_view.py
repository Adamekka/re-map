"""Browser schematic for visited Mansion 1F rooms."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from games.game_profile import RoomId
from tracker.exploration_state import Tracker

REPO = Path(__file__).resolve().parents[2]
MAP_PROFILE_ID = "re1_directors_cut_slus00551"
logger = logging.getLogger(__name__)


def mansion_graph() -> dict:
    # The existing DOT graph normalizes names into one word, so display names live separately.
    dot = (REPO / "data/mansion1f.dot").read_text()
    names = json.loads((REPO / "data/mansion1f_names.json").read_text())
    nodes = set(re.findall(r'^  "([0-9A-F]{2})" \[label=', dot, re.MULTILINE))
    directed = {
        (source, target)
        for source, target in re.findall(
            r'^  "([0-9A-F]{2})" -> "([0-9A-F]{2})";', dot, re.MULTILINE
        )
    }
    if nodes != set(names) or any(
        a not in nodes or b not in nodes for a, b in directed
    ):
        raise ValueError("Mansion 1F graph and room names disagree")
    # The schematic shows connections, not the direction of door scripts.
    adjacent: dict[str, set[str]] = defaultdict(set)
    for source, target in directed:
        adjacent[source].add(target)
        adjacent[target].add(source)
    depth = {"06": 0}
    pending = deque(["06"])
    while pending:
        source = pending.popleft()
        for target in sorted(adjacent[source]):
            if target not in depth:
                depth[target] = depth[source] + 1
                pending.append(target)
    if set(depth) != nodes:
        raise ValueError("Mansion 1F graph has disconnected rooms")

    columns: dict[int, list[str]] = defaultdict(list)
    for room, rank in depth.items():
        columns[rank].append(room)
    positions = {}
    for rank, rooms in columns.items():
        for index, room in enumerate(sorted(rooms)):
            positions[room] = {
                "x": 120 + rank * 230,
                "y": 380 + (index - (len(rooms) - 1) / 2) * 84,
            }
    return {
        "rooms": [
            {"id": room, "name": names[room], **positions[room]}
            for room in sorted(nodes)
        ],
        "edges": [
            list(edge) for edge in sorted({tuple(sorted(edge)) for edge in directed})
        ],
    }


def map_state(tracker: Tracker, item_labels: dict[RoomId, str]) -> dict:
    current = tracker.current
    if current is None:
        return {"status": "waiting", "current": None, "rooms": []}
    rooms = []
    if current.stage == 0:
        for key, record in sorted(tracker.rooms.items()):
            stage, room = key.split("-", 1)
            if stage != "00" or not record.visited:
                continue
            # VISITED is a neutral map state: completion left behind may be stale after a load.
            state = record.completion.value if key == str(current) else "VISITED"
            rooms.append({"id": room.upper(), "state": state})
    record = tracker.room_state(current)
    label = item_labels.get(current) if record.total_items else None
    return {
        "status": "display",
        "current": str(current),
        "rooms": rooms,
        "completion": record.completion.value,
        "known_item": label,
        "known_items": record.total_items,
        "collected_items": record.collected_items,
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
    :root { color-scheme: dark; font: 16px system-ui, sans-serif; background: #101820; color: #eef4f7; }
    body { margin: 0; }
    header { padding: 20px 24px 12px; display: flex; flex-wrap: wrap; gap: 12px 32px; align-items: baseline; }
    h1 { font-size: 22px; margin: 0; }
    #place { font-size: 15px; color: #b9cad4; }
    #status { padding: 0 24px 12px; color: #b9cad4; min-height: 24px; }
    #map-shell { margin: 0 24px; border: 1px solid #344653; border-radius: 12px; background: #15222c; overflow: auto; }
    svg { display: block; width: 100%; min-width: 900px; height: min(68vh, 720px); min-height: 410px; }
    .edge { stroke: #627a88; stroke-width: 3; }
    .room rect { fill: #52616b; stroke: #aab9c2; stroke-width: 1.5; rx: 9; }
    .room.UNKNOWN rect { fill: #785b28; }
    .room.INCOMPLETE rect { fill: #91463f; }
    .room.CLEARED rect { fill: #2f7257; }
    .room.current rect { stroke: #61d5ff; stroke-width: 5; }
    .room text { fill: #fff; font-family: system-ui, sans-serif; pointer-events: none; }
    .room .number { font-size: 13px; font-weight: 700; }
    .room .name { font-size: 14px; }
    #details { padding: 16px 24px 10px; min-height: 52px; }
    #legend { display: flex; flex-wrap: wrap; gap: 12px 22px; padding: 0 24px 24px; color: #c9d7df; font-size: 14px; }
    .key { display: inline-block; width: 15px; height: 15px; border-radius: 3px; margin-right: 7px; vertical-align: -2px; }
  </style>
</head>
<body>
  <header><h1>Room map</h1><span id="place">Waiting for game</span></header>
  <div id="status" role="status">Connect the tracker to begin.</div>
  <div id="map-shell"><svg id="map" role="img" aria-label="Rooms visited in Mansion 1F"></svg></div>
  <div id="details"></div>
  <div id="legend">
    <span><i class="key" style="background:#52616b"></i>Visited</span>
    <span><i class="key" style="background:#785b28"></i>Item status unknown</span>
    <span><i class="key" style="background:#91463f"></i>Items remain</span>
    <span><i class="key" style="background:#2f7257"></i>Cleared</span>
    <span><i class="key" style="background:#15222c;border:3px solid #61d5ff;box-sizing:border-box"></i>Current room</span>
  </div>
  <script>
    const graph = __GRAPH__;
    const byId = new Map(graph.rooms.map(room => [room.id, room]));
    const svg = document.getElementById('map');
    const ns = 'http://www.w3.org/2000/svg';
    let lastReportedError = '';
    function reportError(source, error) {
      const details = {
        source,
        message: (error instanceof Error ? error.message : String(error)).slice(0, 500),
        stack: (error instanceof Error && typeof error.stack === 'string' ? error.stack : '').slice(0, 2000),
      };
      const body = JSON.stringify(details);
      // Stack traces can vary between polls of the same failure.
      const key = JSON.stringify([source, details.message]);
      if (key === lastReportedError) return;
      lastReportedError = key;
      console.error('Room map error', details);
      fetch('/client-error', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })
        .then(response => {
          if (!response.ok) {
            lastReportedError = '';
            console.error('Could not record room map error:', response.status);
          }
        })
        .catch(error => {
          // A failed send must allow the next occurrence to retry.
          lastReportedError = '';
          console.error('Could not record room map error:', error);
        });
    }
    window.addEventListener('error', event => reportError('window', event.error instanceof Error ? event.error : event.message));
    window.addEventListener('unhandledrejection', event => reportError('promise', event.reason));
    function element(tag, attrs) {
      const node = document.createElementNS(ns, tag);
      for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
      return node;
    }
    function draw(state) {
      const place = document.getElementById('place');
      const status = document.getElementById('status');
      const details = document.getElementById('details');
      svg.replaceChildren();
      if (state.status !== 'display') {
        place.textContent = 'Waiting for game';
        status.textContent = 'The tracker is waiting for a readable room.';
        details.textContent = '';
        return;
      }
      const firstFloor = state.current.startsWith('00-');
      place.textContent = firstFloor ? 'Mansion 1F schematic' : 'Room ' + state.current;
      if (!firstFloor) {
        status.textContent = 'Current room: ' + state.current + '. A schematic for this area is not available yet.';
        details.textContent = '';
        return;
      }
      const visible = new Map(state.rooms.filter(room => byId.has(room.id)).map(room => [room.id, room]));
      const currentId = state.current.slice(3).toUpperCase();
      if (!visible.has(currentId)) {
        status.textContent = 'Current room: ' + state.current + '. This room is not in the Mansion 1F schematic.';
      } else {
        status.textContent = visible.size + (visible.size === 1 ? ' room' : ' rooms') + ' visited this session.';
      }
      for (const [a, b] of graph.edges) {
        if (!visible.has(a) || !visible.has(b)) continue;
        const start = byId.get(a), end = byId.get(b);
        svg.append(element('line', { x1: start.x, y1: start.y, x2: end.x, y2: end.y, class: 'edge' }));
      }
      for (const [id, visit] of visible) {
        const room = byId.get(id);
        const group = element('g', { class: 'room ' + visit.state + (id === currentId ? ' current' : '') });
        group.append(element('rect', { x: room.x - 94, y: room.y - 31, width: 188, height: 62 }));
        const number = element('text', { x: room.x - 82, y: room.y - 6, class: 'number' });
        number.textContent = '00-' + id;
        group.append(number);
        const name = element('text', { x: room.x - 82, y: room.y + 15, class: 'name' });
        name.textContent = room.name;
        group.append(name);
        svg.append(group);
      }
      if (visible.size) {
        const rooms = [...visible.keys()].map(id => byId.get(id));
        const left = Math.min(...rooms.map(room => room.x)) - 140;
        const right = Math.max(...rooms.map(room => room.x)) + 140;
        const top = Math.min(...rooms.map(room => room.y)) - 85;
        const bottom = Math.max(...rooms.map(room => room.y)) + 85;
        const width = Math.max(620, right - left), height = Math.max(360, bottom - top);
        svg.setAttribute('viewBox', [(left + right - width) / 2, (top + bottom - height) / 2, width, height].join(' '));
      }
      const labels = { VISITED: 'Visited', UNKNOWN: 'Item status unknown', INCOMPLETE: 'Items remain', CLEARED: 'Cleared' };
      const parts = ['Current room: ' + state.current, labels[state.completion] || 'Item status unknown'];
      if (state.known_item) parts.push(state.known_item + ': ' + state.collected_items + ' of ' + state.known_items + ' collected');
      details.textContent = parts.join(' · ');
    }
    async function refresh() {
      try {
        const response = await fetch('/state', { cache: 'no-store' });
        if (!response.ok) throw new Error('map state request failed: HTTP ' + response.status);
        draw(await response.json());
        lastReportedError = '';
      } catch (error) {
        reportError('refresh', error);
        svg.replaceChildren();
        document.getElementById('details').textContent = '';
        document.getElementById('status').textContent = 'Map connection interrupted.';
      }
    }
    refresh();
    setInterval(refresh, 500);
  </script>
</body>
</html>
"""
