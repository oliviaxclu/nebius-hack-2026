import json

from prime import cites, db
from prime.evidence import evidence_id, search_evidence
from prime.evidence_data import P
from prime.llm import LLM
from prime.config import Settings
from prime.privacy import Redactor
from tests.fakes import ScriptedClient, text_msg


def test_evidence_library_integrity():
    assert len(P) >= 35
    ids = [evidence_id(p["title"]) for p in P]
    assert len(set(ids)) == len(ids)
    for p in P:
        assert p["url"].startswith("http") and p["evidence_level"] and 60 < len(p["text"]) < 900, p["title"]
        assert '"' not in p["text"] or p["text"].count('"') % 2 == 0


def test_retrieval_hits_expected_topic(loaded):
    conn, _, _ = loaded
    cases = {
        "why am I high in the afternoon on prednisone": "steroid", "my morning numbers are high": "dawn",
        "does placenta hormone cause morning highs": "gestational", "what does Ozempic do to meals": "glp1",
        "the second needle cap on my insulin pen": "pen", "sudden low at 3am while sleeping on my arm": "cgm-artifact",
        "should I eat protein before carbs": "meal-order", "can blind people use an insulin pen": "accessibility",
        "does poor sleep raise my glucose": "sleep", "what is time in range": "cgm-metrics", "after dinner walk": "activity",
        "steroid taper and hypoglycemia": "steroid",
    }
    for q, topic in cases.items():
        topics = [r["topic"] for r in search_evidence(conn, q, k=3)]
        assert topic in topics, (q, topics)


def test_placenta_question_returns_the_correction_first(loaded):
    conn, _, _ = loaded
    top = search_evidence(conn, "do placental hormones cause my high morning glucose", k=3)[0]
    assert top["topic"] == "gestational" and "pregnancy" in top["text"]


def test_redactor_identifiers_and_clinical_content():
    ident = {"name": ["Ray Hale", "Ray", "Hale"], "dob": ["1957-06-14"], "mrn": ["MRN-0172264"], "phone": ["415-555-0188"],
             "email": ["ray.hale@example.com"]}
    r = Redactor(ident)
    out = r.redact("Ray Hale (DOB 06/14/1957, MRN-0172264) 415-555-0188 ray.hale@example.com SSN 123-45-6789")
    for secret in ("Ray", "Hale", "1957", "0172264", "555-0188", "example.com", "123-45"):
        assert secret not in out
    clinical = "Fasting 203 mg/dL on 2026-09-25 after 18 units of glargine and prednisone 30 mg"
    assert r.redact(clinical) == clinical


def test_everything_sent_to_the_model_is_redacted_and_audited(loaded):
    conn, tb, _ = loaded
    client = ScriptedClient([text_msg("ok")])
    s = Settings(home=tb.ics_path.parent, api_key="k", base_url="http://x", model="nvidia/test")
    llm = LLM(s, conn, Redactor(db.load_identity(conn)), client=client)
    llm.chat([{"role": "user", "content": "I'm Ray Hale, MRN-0172264. Why was I high?"}], purpose="test")
    sent = json.dumps(client.requests[0])
    assert "Ray" not in sent and "Hale" not in sent and "0172264" not in sent and "[PATIENT]" in sent
    row = conn.execute("SELECT sent FROM llm_audit").fetchone()["sent"]
    assert "[PATIENT]" in row and "Hale" not in row


def test_cites_find_and_verify(loaded):
    conn, _, _ = loaded
    text = "See [day:2026-09-25], [ins:1], [src:deadbeef], [ins:99999], [meal:3] and [note:1]."
    v = cites.verify(conn, text)
    assert v["day:2026-09-25"] and v["ins:1"] and v["meal:3"]
    assert v["src:deadbeef"] is None and v["ins:99999"] is None and "note:1" not in v


def test_cites_normalize_alt_brackets(loaded):
    conn, _, _ = loaded
    text = cites.normalize("Low on 【day:2026-09-25】 after ［ins:1］ and 【 meal:3 】; see 【check_dose_response】.")
    assert text == "Low on [day:2026-09-25] after [ins:1] and [meal:3]; see 【check_dose_response】."
    v = cites.verify(conn, text)
    assert v["day:2026-09-25"] and v["ins:1"] and v["meal:3"]
