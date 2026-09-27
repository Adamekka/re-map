"""Schematic topology and local map delivery."""

import http.client
import json
import sys
from pathlib import Path
from threading import Thread

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from tracker.exploration_state import Tracker
from ui.map_view import MapServer, mansion_graph, map_state


def test_mansion_graph_uses_known_first_floor_connections():
    graph = mansion_graph()
    rooms = {room["id"]: room for room in graph["rooms"]}
    assert len(rooms) == 27
    assert rooms["09"]["name"] == "Winding Passage"
    assert ["08", "09"] in graph["edges"]
    assert len(graph["edges"]) == 26
    assert "10" not in rooms  # No source room file for this target yet.
    assert len({(room["x"], room["y"]) for room in rooms.values()}) == len(rooms)


def test_map_starts_without_revealed_rooms():
    assert map_state(Tracker(), {}) == {
        "status": "waiting",
        "current": None,
        "rooms": [],
    }


def test_map_server_serves_page_and_current_snapshot():
    server = MapServer(0, mansion_graph())
    assert server.server_address[0] == "127.0.0.1"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        connection.request("GET", "/")
        response = connection.getresponse()
        page = response.read().decode()
        assert response.status == 200
        assert "Winding Passage" in page
        connection.close()

        snapshot = {
            "status": "display",
            "current": "00-09",
            "rooms": [{"id": "09", "state": "INCOMPLETE"}],
        }
        server.snapshot = json.dumps(snapshot).encode()
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        connection.request("GET", "/state")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Cache-Control") == "no-store"
        assert json.loads(response.read()) == snapshot
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
