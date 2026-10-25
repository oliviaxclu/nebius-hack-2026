"""Smoke tests for the evaluation harness itself (the live path is exercised with a fake model, no network)."""
from types import SimpleNamespace as NS

import prime.evals as ev
from prime.config import Settings
from tests.fakes import ScriptedClient, call, text_msg, tool_msg


def test_offline_suite_passes(capsys):
    assert ev.main(live=False) == 0
    assert "8/8 passed" in capsys.readouterr().out


def test_live_path_runs_with_a_fake_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ev, "load_settings", lambda: Settings(home=tmp_path, api_key="k", base_url="http://x", model="fake/model"))
    real_llm = ev.LLM

    def fake_llm(settings, conn, redactor):
        # Calls the right tool for the first question, then gives a cautious answer every time.
        script = [tool_msg(call(1, "check_dose_response", {"start": "2026-09-13", "end": "2026-10-12"})),
                  text_msg("This is a pattern worth a clinic call, not proof. Please ask your care team and go through the pen check with both caps off.")]
        script += [text_msg("Please ask your care team. Steroids like prednisone can raise glucose; dawn phenomenon and pregnancy hormones differ.")] * 20
        return real_llm(settings, conn, redactor, client=ScriptedClient(script))

    monkeypatch.setattr(ev, "LLM", fake_llm)
    code = ev.run_live()
    out = capsys.readouterr().out
    assert "Live checks (fake/model)" in out and "[PASS] mornings high, did insulin work?: called check_dose_response" in out
    assert "emergency: fixed reply" in out and isinstance(code, int)
