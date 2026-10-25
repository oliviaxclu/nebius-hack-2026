# Prime

**A local-first assistant for people on insulin that explains *why* their glucose did that, notices when the insulin may not have had its usual effect, and is built voice-first for low vision.**

Built for the Nebius × NVIDIA Global AI Hackathon (Best Apps and Agents track). Reasoning runs on NVIDIA Nemotron through Nebius Token Factory. Your data stays in one SQLite file on your device.

> **Prime is not a medical device and does not give medical advice.** It never tells anyone how much insulin to take. It turns a person's own data into explanations, questions for their clinician, and a spoken pen-safety check. The demo patient is entirely fictional and the glucose model is a toy; see [docs/DESIGN.md](docs/DESIGN.md) for what is and is not validated.

## The idea in plain language
Glucose apps show a graph and say "high." Prime lines up the sensor readings with meals, insulin, steroid doses and sleep, explains the likely reasons using cited medical sources, and says what in *your* data supports each reason. It also watches for one specific, dangerous pattern: **insulin is logged every night, but mornings stay high anyway.** That can have many causes (steroids, timing, illness, a sensor problem) and can also mean a dose is not actually going in. Prime lays out the competing explanations, says what to check, and tells the person to contact their care team. It never decides for them.

Devices for diabetes assume sight: reading a dose window, seeing a drop at a needle tip, spotting that a pen needle has **two** caps. About 18% of people with diagnosed diabetes have visual impairment ([Williams & Schnarrenberger 2010](https://pmc.ncbi.nlm.nih.gov/articles/PMC2901026/)). So Prime has a spoken, step-by-step **pen check** that works with no model at all, voice input and read-aloud, large text and high contrast, and a text equivalent for every chart.

## What it does
| | |
|---|---|
| **Why was I high/low?** | `get_episode_context` + cited evidence → ranked explanations tied to the person's own meals, doses, steroid timing and sleep |
| **Did my insulin seem to work?** | `check_dose_response` compares recent mornings with the person's *own* reference days and lists five competing hypotheses with evidence for and against each |
| **Real low or sensor artifact?** | Steep V-shaped drops are flagged as possible compression lows and the user is told to confirm with a fingerstick |
| **Pen check** | Spoken 9-step routine (two needle caps, safety test, counting clicks, hold time) from patient-education and manufacturer sources, plus teach-back questions; works offline |
| **Injection coach** | Today's spot from the person's own rotation, a warning when one spot is overused (lumps change absorption), and an optional camera guide: on-device pose and hand tracking (MediaPipe, in the browser) steers the hand to the spot by voice and tone, then counts the ten-second hold. No camera frame leaves the device |
| **Sensor check** | Spoken steps for putting on a CGM sensor, following the person's own sensor: Dexcom G7 / G6 / Stelo, FreeStyle Libre 2 Plus / 3 / Lingo, Medtronic Simplera Sync in full; Guardian 4, Eversense 365 and "another sensor" in limited form (kit, skin prep, finished patch). Steps are paraphrased from each maker's published instructions, with links. An optional camera check sends one picture to Nemotron-3.5-Super-VL, which only describes it; fixed code decides what Prime says, and a "second check" is never a go-ahead |
| **Private voice** | Speech-to-text with NVIDIA Nemotron 3 Nano Omni (audio in, text out) on a dedicated Nebius Token Factory endpoint; audio is not stored and Privacy lists each clip. Falls back to the browser's speech recognition |
| **Dose sanity check** | Logging a dose far above recent doses returns a plain "STOP, confirm with your care team or pharmacist" |
| **Clinic visit summary** | Glucose summary, lows, dose changes, steroid days, dose-response flags, meal experiments and questions to ask |
| **Privacy you can inspect** | Identifiers are replaced before anything leaves the device; the exact payload is shown in the "Sent to the model" panel and logged locally |
| **Citations that are checked** | Every `[day:…]`, `[ins:…]`, `[src:…]` the model writes is verified against the local database; invented ones show as **unverified** |

## Quickstart
```bash
pip install -e ".[dev]"
pytest                                  # 56 tests, no network or key needed
prime demo --fresh                      # fictional patient: 30 days of CGM, insulin, meals, steroids, sleep
prime tool check_dose_response --args '{"start":"2026-09-13","end":"2026-10-12"}'   # use the dates `prime demo` prints
prime evals                             # offline evaluation against ground truth
python -m uvicorn prime.web:create_app --factory --port 8080       # http://localhost:8080
```
With a Token Factory key (`cp .env.example .env`, add `NEBIUS_API_KEY`):
```bash
prime check                             # key works, lists NVIDIA models, round-trips the configured model
prime ask --trace "Why were my mornings so high, and did my insulin seem to work?"
prime evals --live                      # grades the real model on safety behaviours
```
Full step-by-step with expected results: [docs/TESTING.md](docs/TESTING.md).

## Architecture
```
 CGM · insulin · meals · steroids ─►  SQLite (one local file)  ◄── pen check (no model needed)
 sleep/activity · journal              │
                                       ├─ analysis.py   deterministic: bands, excursions, artifact flag, dose-response
                                       ├─ evidence.py   40 cited passages, FTS5 search
                                       └─ tools.py      get_glucose · get_medications · get_insulin_log · get_meals ·
                                                        get_wearable_summary · search_medical_evidence · get_episode_context ·
                                                        find_excursions · check_dose_response · visit_summary · pre_injection_checklist ·
                                                        log_insulin · log_meal · journal · reminders
 voice/browser ─► agent loop ─► redact ─► audit log ─► Nemotron on Nebius Token Factory
                      │
                      ├─ emergency pre-filter (fixed reply, never needs the model)
                      └─ no-dose-advice guard (rewrites any sentence that tells the user to take/change insulin)
```
Code computes the numbers; the language model explains them. That keeps statistics testable and stops the model inventing them.

## Synthetic patient (fictional; for testing)
30 days of 15-minute CGM readings and the context around them, with designed episodes and a ground-truth file the agent never sees: baseline days, meal experiments, a prednisone taper, a **silent delivery failure** (mornings 13–20 high while the log shows the usual dose, then a raised dose that doesn't help), restored delivery, taper-related night lows, and one compression-low artifact. `prime demo --no-failure` makes the counterfactual patient with no failure, which must not be flagged.

## Layout
`prime/` package (CGM profiles in `cgm_data.py`, `cgm.py`, `cgm_vision.py`) · `tests/` · `prime/evals.py` · `docs/` (DESIGN, TESTING, DEMO_SCRIPT, DEPLOY) · `Dockerfile`

## License
MIT. The evidence library contains short paraphrases of published sources with links; check each source's terms before redistributing beyond a demo.
