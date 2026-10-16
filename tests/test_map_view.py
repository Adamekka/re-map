"""Floor-plan geometry and local map delivery."""

import http.client
import json
import sys
from pathlib import Path
from threading import Thread

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from games.game_profile import RoomId
from tracker.exploration_state import DoorDetail, ItemDetail, Tracker
from ui.map_view import MapRequestHandler, MapServer, map_state


def catalog():
    return json.loads((REPO / "data/floor_plans_slus00551.json").read_text())


def test_mansion_floor_plan_uses_architectural_shapes_and_wall_doors():
    plan = catalog()["areas"][0]
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


def test_map_exposes_only_explored_floors_with_fresh_item_and_door_details():
    tracker = Tracker(player_heading=90.0)
    herb_room, upper_room = RoomId(0, 9), RoomId(1, 3)
    for room, region in (
        (herb_room, "mansion1f:09"),
        (upper_room, "mansion2f:03"),
    ):
        tracker.mark_current(room)
        tracker.region_visits[region] = str(room)
        tracker.update_room_items(room, 1, 0, True, True, False)
        tracker.rooms[str(room)].items = (ItemDetail("Green Herb", "available", 1),)
    tracker.current_region = "mansion2f:03"
    tracker.doors = (
        DoorDetail(herb_room, upper_room, "LOCKED", "Locked", key_label="Armor Key"),
    )

    state = map_state(tracker)
    assert set(state["explored_areas"]) == {"mansion1f", "mansion2f"}
    assert state["rooms"] == state["explored_areas"]["mansion2f"]
    assert [room["id"] for room in state["explored_areas"]["mansion1f"]] == ["09"]
    assert [room["id"] for room in state["explored_areas"]["mansion2f"]] == ["03"]
    assert state["explored_areas"]["mansion1f"][0]["state"] == "INCOMPLETE"
    assert state["explored_areas"]["mansion1f"][0]["items_complete"] is True
    assert state["doors"][0]["state"] == "LOCKED"
    assert state["doors"][0]["key_label"] == "Armor Key"

    # A loaded game's fresh verdicts must update a browsable departed floor too.
    tracker.update_room_items(herb_room, 1, 1, True, False, False)
    tracker.rooms[str(herb_room)].items = (ItemDetail("Green Herb", "taken", 1),)
    tracker.doors = (DoorDetail(herb_room, upper_room, "OPEN", "Unlocked"),)
    state = map_state(tracker)
    previous_floor = state["explored_areas"]["mansion1f"][0]
    assert previous_floor["state"] == "CLEARED"
    assert previous_floor["items"][0]["state"] == "taken"
    assert state["doors"][0]["state"] == "OPEN"


def test_unoutlined_current_floor_can_follow_without_revealing_rooms():
    tracker = Tracker(player_heading=90.0)
    tracker.mark_current(RoomId(0, 9))
    tracker.region_visits = {"mansion1f:09": "00-09"}
    tracker.mark_current(RoomId(4, 0x15))
    tracker.current_region = "laboratoryb4:15"
    state = map_state(tracker)
    assert state["area"] == "laboratoryb4"
    assert state["explored_areas"]["laboratoryb4"] == []
    assert len(state["explored_areas"]["mansion1f"]) == 1
    assert state["current_detail"]["room"] == "04-15"
    assert state["rooms"] == []


def test_remaining_items_do_not_imply_complete_item_checks():
    tracker = Tracker(player_heading=90.0)
    room = RoomId(0, 9)
    tracker.mark_current(room)
    tracker.current_region = "mansion1f:09"
    tracker.region_visits[tracker.current_region] = str(room)
    tracker.update_room_items(room, 1, 0, False, True, True)
    tracker.rooms[str(room)].items = (ItemDetail("Green Herb", "available", 1),)
    tracker.rooms[str(room)].reason = "Other item conditions remain unresolved."
    detail = map_state(tracker)["explored_areas"]["mansion1f"][0]
    assert detail["state"] == "INCOMPLETE"
    assert detail["items_complete"] is False
    assert detail["items"][0]["state"] == "available"


def test_map_server_serves_page_and_current_snapshot(caplog):
    server = MapServer(0, catalog())
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
        assert "Check incomplete" in page
        assert ".room.UNKNOWN path" in page
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
    server = MapServer(0, catalog())
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
    server = MapServer(0, catalog())
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
