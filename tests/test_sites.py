from prime import cites, sites
from prime.agent import enforce_no_dose_advice
from tests.test_web import make_client

B = sites.AREAS["belly"]


def test_suggest_stays_in_the_area_and_picks_the_spot_used_longest_ago():
    assert sites.suggest([]) == "belly-upper-right"                                    # start of the clock
    assert sites.suggest(["belly-upper-right"]) == "belly-lower-right"                 # never-used spots first, in clock order
    assert sites.suggest(["belly-lower-left", "belly-upper-left", "belly-upper-right", "belly-lower-right"]) == "belly-lower-right"
    assert sites.suggest(["thigh-right"]) == "thigh-left"                              # stays in the thigh area
    assert sites.suggest(["thigh-right"], area="belly") == "belly-upper-right"


def test_overuse_needs_five_of_the_last_seven():
    assert sites.overuse(["belly-lower-right"] * 4) is None
    o = sites.overuse(["belly-lower-right"] * 5 + ["belly-upper-left"] * 2 + ["belly-lower-right"] * 9)
    assert o == {"zone": "belly-lower-right", "where": sites.ZONES["belly-lower-right"], "count": 5, "of": 7}
    assert sites.overuse(B + B) is None


def test_demo_patient_overuses_one_spot_and_gets_a_cited_warning(loaded):
    conn, tb, _ = loaded
    r = tb.get_injection_sites()
    assert r["overuse"]["zone"] == "belly-lower-right" and r["overuse"]["count"] >= 5
    assert r["suggested_next"]["zone"] != "belly-lower-right"
    assert r["overuse"]["src"] and all(c["src"] for c in r["checks"])
    assert cites.verify(conn, "[%s]" % r["recent"][0]["cite"])[r["recent"][0]["cite"]].startswith("Injection site")
    for line in [r["overuse"]["say"], *(c["say"] for c in r["checks"])]:
        assert enforce_no_dose_advice(line)[1] == [], line


def test_log_site_validates_and_reads_back(loaded):
    _, tb, _ = loaded
    assert tb.log_injection_site("elbow")["logged"] is False
    r = tb.log_injection_site("thigh-left")
    assert r["logged"] and "left thigh" in r["readback"]
    assert tb.get_injection_sites()["recent"][0]["zone"] == "thigh-left"


def test_site_endpoints(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/api/sites").json()["overuse"]["zone"] == "belly-lower-right"
    r = c.post("/api/sites", json={"zone": "belly-upper-left"}).json()
    assert r["logged"] and c.get("/api/record/" + r["cite"]).status_code == 200
    assert c.post("/api/sites", json={"zone": "nose"}).status_code == 422
