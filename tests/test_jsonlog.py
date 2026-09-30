import io
import json
import logging

from app import jsonlog


def test_every_line_has_run_id_and_drops_unlisted_fields() -> None:
    buf = io.StringIO()
    jsonlog.configure(stream=buf)
    rid = jsonlog.set_run(snapshot_id="nba_20260930")
    log = logging.getLogger("t")
    log.info("hello", extra={"event": "x", "question": "who is my neighbour", "email": "a@b.c"})
    log.warning("again")
    lines = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert len(lines) == 2
    for line in lines:
        assert line["run_id"] == rid
        assert line["snapshot_id"] == "nba_20260930"
        assert "question" not in line
        assert "email" not in line
    assert lines[0]["event"] == "x"
