"""
dashboard_api.py — SENTINEL Dashboard API
Run: python dashboard_api.py
Open: http://localhost:5000
"""

import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, send_from_directory
from storage.db import init_db, get_connection, verify_event_chain, get_events, get_audit_log

app = Flask(__name__)
REPORTS_DIR = Path("reports")


# Allow browser to call API from same origin
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.route("/")
def index():
    return send_from_directory(".", "dashboard.html")


@app.route("/api/sessions")
def sessions():
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    session_id,
                    MIN(timestamp) as started,
                    MAX(timestamp) as ended,
                    COUNT(*) as event_count
                FROM events
                WHERE session_id IS NOT NULL
                  AND session_id != ''
                GROUP BY session_id
                ORDER BY started DESC
                LIMIT 20
            """).fetchall()
        data = [dict(r) for r in rows]
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/session/<session_id>")
def session_detail(session_id):
    try:
        events  = get_events(session_id)
        audit   = get_audit_log(session_id)
        chain_ok = verify_event_chain(session_id)

        # Phase summary
        phases_seen = {}
        for e in events:
            p = e["phase"]
            if p in ("init", "final", "memory"):
                continue
            if p not in phases_seen:
                phases_seen[p] = {
                    "phase": p, "events": 0,
                    "successes": 0, "errors": 0, "status": "ran"
                }
            phases_seen[p]["events"] += 1
            if e["event_type"] == "TOOL_SUCCESS":
                phases_seen[p]["successes"] += 1
            if e["event_type"] in ("TOOL_ERROR", "PARSE_ERROR", "LLM_ERROR"):
                phases_seen[p]["errors"] += 1
            if e["event_type"] == "PHASE_COMPLETE":
                phases_seen[p]["status"] = "success"

        # Termination
        termination = "UNKNOWN"
        for e in reversed(events):
            if e["event_type"] == "SESSION_END":
                payload = json.loads(e["payload"])
                termination = payload.get("termination", "UNKNOWN")
                break

        # Topic
        topic = ""
        for e in events:
            if e["event_type"] == "SESSION_START":
                topic = json.loads(e["payload"]).get("topic", "")
                break

        # Started / ended
        started = events[0]["timestamp"] if events else ""
        ended   = events[-1]["timestamp"] if events else ""

        return jsonify({
            "session_id":     session_id,
            "topic":          topic,
            "termination":    termination,
            "chain_integrity": chain_ok,
            "total_events":   len(events),
            "audit_events":   len(audit),
            "started":        started,
            "ended":          ended,
            "phases":         list(phases_seen.values()),
            "recent_events": [
                {
                    "timestamp":       e["timestamp"],
                    "phase":           e["phase"],
                    "event_type":      e["event_type"],
                    "payload_preview": e["payload"][:120]
                }
                for e in events[-25:]
            ],
            "audit_log": [
                {
                    "timestamp":  a["timestamp"],
                    "event_type": a["event_type"],
                    "detail":     a["detail"][:200]
                }
                for a in audit
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/report/<session_id>")
def report(session_id):
    try:
        path = REPORTS_DIR / f"report_{session_id}.md"
        if not path.exists():
            return jsonify({"content": None})
        content = path.read_text(encoding="utf-8")
        return jsonify({"content": content, "path": str(path)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    init_db()
    print("\n  SENTINEL dashboard → http://localhost:5000\n")
    app.run(debug=False, port=5000, threaded=True)