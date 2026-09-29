"""Floor-plan geometry and local map delivery."""

import http.client
import json
import sys
from pathlib import Path
from threading import Thread

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from tracker.exploration_state import Tracker
from ui.map_view import MapRequestHandler, MapServer, mansion_floor_plan, map_state


def test_mansion_floor_plan_uses_architectural_shapes_and_wall_doors():
    plan = mansion_floor_plan()
    rooms = {room["id"]: room for room in plan["rooms"]}
    assert len(rooms) == 32
    assert rooms["09"]["name"] == "Winding Passage"
    assert len(rooms["09"]["rings"][0]) > 4
    assert len(plan["doors"]) == 28
    assert any(door["rooms"] == ["08", "09"] for door in plan["doors"])
    assert "edges" not in plan


def test_map_starts_without_revealed_rooms():
    assert map_state(Tracker()) == {
        "status": "waiting",
        "current": None,
        "rooms": [],
    }


def test_map_server_serves_page_and_current_snapshot(caplog):
    server = MapServer(0, mansion_floor_plan())
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
        assert "HTTP" not in caplog.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_map_records_browser_errors_and_rejects_invalid_reports(caplog):
    server = MapServer(0, mansion_floor_plan())
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        error = {
            "source": "refresh",
            "message": "failed to draw\nforged entry",
            "stack": "draw at map:100",
        }
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        connection.request(
            "POST",
            "/client-error",
            json.dumps(error),
            {"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        assert response.status == 204
        response.read()
        connection.close()
        assert "Browser error:" in caplog.text
        assert "draw at map:100" in caplog.text
        assert "draw\\nforged entry" in caplog.text
        assert "draw\nforged entry" not in caplog.text

        for body, content_type, expected in (
            (json.dumps(error), "text/plain", 415),
            ("", "application/json", 400),
            ("x" * 8193, "application/json", 413),
            ("{", "application/json", 400),
            ("[" * 2000 + "]" * 2000, "application/json", 400),
            ('{"source":1,"message":"bad","stack":""}', "application/json", 400),
        ):
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=3
            )
            connection.request(
                "POST", "/client-error", body, {"Content-Type": content_type}
            )
            response = connection.getresponse()
            assert response.status == expected
            response.read()
            connection.close()
        assert "HTTP 127.0.0.1:" in caplog.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_map_handler_exceptions_keep_traceback(caplog, monkeypatch):
    def fail_request(self):
        raise RuntimeError("injected map failure")

    monkeypatch.setattr(MapRequestHandler, "do_GET", fail_request)
    server = MapServer(0, mansion_floor_plan())
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=3
        )
        connection.request("GET", "/")
        with pytest.raises(http.client.RemoteDisconnected):
            connection.getresponse()
        connection.close()
        assert "Map request failed" in caplog.text
        assert "Traceback" in caplog.text
        assert "RuntimeError: injected map failure" in caplog.text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
