# Design notes, safety stance, and honest limits

## Principles
1. **Explain, don't instruct.** The assistant never advises on insulin or other doses. Two layers enforce it: the system prompt, and `enforce_no_dose_advice`, a code-level filter that rewrites any final sentence that tells the user to take, skip, double, increase or reduce insulin (unless it is a refusal or a referral to the care team). The filter is tested, and the live eval counts every time it had to fire.
2. **Code computes, the model explains.** Time in range, excursions, artifact detection and the dose-response comparison are plain Python (`analysis.py`). The model reads their output.
3. **Say what the data can and cannot show.** `check_dose_response` returns five competing hypotheses (insulin didn't have its usual effect, steroid alone, waning/mistimed insulin, Somogyi rebound, sensor/illness/diet), each with evidence for and against computed from the person's own data, plus a `limits` list. It never concludes a dose was missed.
4. **Verify every citation.** Ids in model output are resolved against the local database; unknown ones are shown as *unverified*.
5. **Emergencies and device safety don't need the model.** Chest pain, breathing trouble, unresponsiveness, suicidal statements get a fixed reply from a regex pre-filter (also when the API key is missing). `log_insulin` returns a STOP warning when a dose is ≥1.5× the recent median. The pen check is deterministic.
6. **Accessibility is the product.** Voice in/out, large text, high contrast, a text equivalent for every chart, keyboard operation, no information carried by color alone.

## Heuristics (NOT clinically validated)
- Flag: fasting (05:00–07:00 median) ≥ 35 mg/dL above the person's own reference for ≥ 3 consecutive mornings. Reference = earliest ≥ 4 days before any steroid exposure with logged insulin.
- "Escalation without response": a logged dose ≥ 120% of reference with fasting improved by < 20%.
- Compression-low suspicion: low lasting ≤ 90 min with entry and exit slopes ≥ 1.2 mg/dL per minute.
- Dose sanity warning at ≥ 150% of the recent median dose.
- Bands follow the 2019 international CGM consensus (70–180; <70; <54; >180; >250).

## What was verified, and how
| Area | Status |
|---|---|
| Engine vs ground truth (exact failure window on 6 seeds, no false alarms in the counterfactual, 1 artifact and 5 real lows) | automated (`prime evals`, `pytest`) |
| Citations emitted by tools resolve (113 ids) | automated |
| Web API, sessions, rate limits, redaction, emergency path | automated (FastAPI TestClient) |
| UI rendering functions (escaping, chips, chart, screen-reader text) | tested under Node |
| **The UI in a real browser, with a screen reader, and voice input** | **not yet done; test by hand (see TESTING.md)** |
| **Nemotron on Token Factory: tool calling, answer quality, safety behaviour** | **not yet run; `prime check` and `prime evals --live` do it** |
| Docker image build and Nebius deployment | not yet run |
| Glucose model realism | toy model; for testing only |
| Evidence passages | paraphrased from sources read during the build; not clinician-reviewed |

## Known gaps
- Browser speech recognition and synthesis are not NVIDIA models. Voice through Nemotron 3 Nano Omni (audio in, text out) is the intended upgrade; check it is in your Token Factory catalog.
- Pen steps differ by pen and manufacturer; the checklist is generic and says so.
- No real device integrations (Libre/Dexcom APIs, smart pens). Import is synthetic only.
- The evidence library is small (40 passages). Gaps: hypoglycemia treatment specifics, DKA, illness days, alcohol, exercise intensity, other drug classes.
- Single-patient assumptions in the reference-baseline logic.
