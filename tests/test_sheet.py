import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harvest import sheet  # noqa: E402


class FakeResp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json))
        return FakeResp({"ok": True, "added": len(json["rows"]), "skipped": 0})


def test_post_rows_batches_and_sends_token(monkeypatch):
    monkeypatch.setenv("SHEET_WEBHOOK_URL", "https://script.google.com/macros/s/x/exec")
    monkeypatch.setenv("SHEET_WEBHOOK_TOKEN", "t")
    s = FakeSession()
    rows = [{"post_key": f"NIA:press:{i}", "att_url": f"u{i}"} for i in range(450)]
    assert sheet.post_rows(rows, session=s) == {"added": 450, "skipped": 0}
    assert len(s.calls) == 3 and all(c[1]["token"] == "t" for c in s.calls)


def test_post_rows_rejects_unknown_field(monkeypatch):
    monkeypatch.setenv("SHEET_WEBHOOK_URL", "u")
    monkeypatch.setenv("SHEET_WEBHOOK_TOKEN", "t")
    with pytest.raises(ValueError):
        sheet.post_rows([{"post_key": "a", "approved": True}], session=FakeSession())


def test_post_rows_needs_env(monkeypatch):
    monkeypatch.delenv("SHEET_WEBHOOK_URL", raising=False)
    with pytest.raises(RuntimeError):
        sheet.post_rows([])
