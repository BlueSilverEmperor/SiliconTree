"""Verification tests for the SiliconTree Flask Web GUI."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web_gui import create_flask_app


def test_flask_gui_all_routes_and_modes() -> None:
    app = create_flask_app()
    client = app.test_client()

    # Main HTML page
    res = client.get("/")
    assert res.status_code == 200
    assert b"SiliconTree" in res.data

    # Initial state + SpectreScope LFENCE + Flush+Reload
    st = client.get("/api/state").get_json()
    assert st["mode_id"] == "spectrescope"
    st = client.post("/api/step", json={"count": 30}).get_json()
    assert st["mode_hud"]["leak_detected"] is True
    st = client.post("/api/spectre/probe", json={}).get_json()
    assert st["mode_hud"]["recovered_secret"] == 5
    st = client.post("/api/spectre/lfence", json={"enabled": True}).get_json()
    assert st["mode_hud"]["lfence_enabled"] is True

    # Rewind & Reset
    st = client.post("/api/step", json={"count": 3}).get_json()
    assert st["snapshot"]["cycle"] == 3
    st = client.post("/api/rewind", json={"count": 1}).get_json()
    assert st["snapshot"]["cycle"] == 2
    st = client.post("/api/reset", json={}).get_json()
    assert st["snapshot"]["cycle"] == 0

    # Switch across all remaining modes
    for mode_id in ("silicon_heist", "silicon_deathmatch", "silicon_forensic", "architect_tycoon", "sandbox"):
        m_res = client.post(f"/api/mode/{mode_id}")
        assert m_res.status_code == 200
        assert m_res.get_json()["mode_id"] == mode_id

    # Tycoon configure + evaluate
    client.post("/api/mode/architect_tycoon")
    t_res = client.post("/api/tycoon/configure", json={"clock_ghz": 2.4, "l1_associativity": 2, "forwarding_enabled": True})
    assert t_res.status_code == 200
    e_res = client.post("/api/tycoon/evaluate", json={}).get_json()
    assert e_res["outcome"]["victory"] is True

