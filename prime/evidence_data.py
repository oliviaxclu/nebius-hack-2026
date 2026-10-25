"""Curated evidence passages for search_medical_evidence.

Each entry is a SHORT PARAPHRASED SUMMARY of a source that was read while building this project.
Nothing is quoted. They are not a substitute for the sources: show the URL, and treat anything the
model says as only as strong as the `evidence_level` label.

Before relying on the library beyond a demo: check each source's license/terms, re-read the source,
and have a clinician review the passages. Add passages the same way (topic, title, source, year,
evidence_level, text, url).
"""

P = []


def add(topic, title, source, year, level, text, url):
    P.append(dict(topic=topic, title=title, source=source, year=year, evidence_level=level, text=text, url=url))


# ---------------------------------------------------------------- morning highs
add("dawn", "Dawn phenomenon: early-morning hormone surge",
    "StatPearls (NCBI Bookshelf)", "2026", "clinical-reference",
    "Cortisol, growth hormone, catecholamines and glucagon rise before dawn (roughly 3 to 8 AM) and increase the liver's "
    "glucose output and insulin resistance. If insulin is lacking or resistance is high, glucose is high on waking. CGM studies "
    "suggest about half of people with type 1 or type 2 diabetes show it. It differs from the Somogyi effect, which follows a "
    "night-time low. Circadian disruption and evening inactivity may make it worse.",
    "https://www.ncbi.nlm.nih.gov/sites/books/NBK430893/")
add("dawn", "Morning highs: dawn phenomenon, waning insulin, Somogyi rebound",
    "American Diabetes Association", "n.d.", "professional-society",
    "The two main causes of morning highs are the dawn phenomenon and waning insulin; a rebound after a night-time low (Somogyi) "
    "is rarer. Looking at overnight CGM helps separate them: rises from about 3 to 8 AM point to dawn. Long-acting insulin that "
    "wears off before the next dose, or is taken early, can also leave mornings high. Raising a long-acting dose to treat dawn "
    "highs can cause lows earlier in the night, so changes belong with the care team.",
    "https://diabetes.org/living-with-diabetes/high-morning-blood-glucose")
add("activity", "Evening activity and overnight glucose",
    "American Diabetes Association", "n.d.", "professional-society",
    "An after-dinner walk or workout can help keep glucose down overnight in people whose insulin wanes. The lowering effect can last "
    "hours, so exercising right before bed can raise the risk of an overnight low; morning exercise may suit people who see lows "
    "after evening exercise. Quantitative data are limited on this page, so treat it as practical guidance, not a measured effect size.",
    "https://diabetes.org/living-with-diabetes/high-morning-blood-glucose")
add("dawn", "Evening protein and activity for dawn highs",
    "Cleveland Clinic", "2025", "consumer-health",
    "Clinicians may suggest more evening exercise and a higher protein-to-carbohydrate ratio in the evening meal for dawn "
    "phenomenon. CGM is the most effective way to detect it. Other causes of high mornings include too little medication, "
    "mistimed doses, and the Somogyi effect.",
    "https://my.clevelandclinic.org/health/diseases/24553-dawn-phenomenon")
add("dawn", "Dawn phenomenon: counter-regulatory hormones",
    "Mayo Clinic", "2022", "consumer-health",
    "Counter-regulatory hormones (growth hormone, cortisol, glucagon, epinephrine) rise overnight and oppose insulin. Not getting "
    "enough insulin the night before, a wrong dose, or a carbohydrate-containing bedtime snack can also raise morning glucose. "
    "Consistently high mornings are worth discussing with a clinician, who may adjust medicine, timing or type.",
    "https://www.mayoclinic.org/diseases-conditions/diabetes/expert-answers/dawn-effect/faq-20057937")
add("gestational", "Placental hormones are a gestational-diabetes mechanism",
    "Primary research article (PMC11488653)", "2024", "primary-research",
    "In gestational diabetes, insulin resistance is driven largely by hormones made by the placenta, including human placental "
    "lactogen, growth hormone, prolactin, CRH and progesterone. That mechanism applies to pregnancy. For a non-pregnant adult, "
    "high mornings are explained by the dawn phenomenon or by insulin timing and dose, not placental hormones.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC11488653/")

# ---------------------------------------------------------------- steroids
add("steroid", "Steroid timing: afternoon and evening highs, fasting can look normal",
    "Management of Glucocorticoid-Induced Hyperglycemia (Diabetes Metab Syndr Obes)", "2022", "review",
    "With a once-daily morning dose of an intermediate-acting steroid such as prednisone, glucose rises most about 4 to 6 hours "
    "later, mostly in the late afternoon and evening. With divided doses or long-acting steroids, highs persist through the day. "
    "Steroids cause larger after-meal rises through insulin resistance, so a fasting reading can look normal while the rest of "
    "the day is high.",
    "https://www.tandfonline.com/doi/full/10.2147/DMSO.S330253")
add("steroid", "Steroid mechanisms: muscle, fat and liver",
    "Practical Guide to Steroid-Induced Hyperglycaemia in the Hospital (PMC8157052)", "2021", "review",
    "Glucocorticoids reduce insulin sensitivity in muscle and fat and increase the liver's glucose production. Insulin needs depend "
    "on which steroid is used, its dose, and when it is given, and they fall as the steroid dose is reduced.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC8157052/")
add("steroid", "Steroid taper: glucose-lowering doses may need to come down in step",
    "Practical Guide to Glucocorticoid Induced Hyperglycaemia and Diabetes (PMC10037401)", "2023", "review",
    "When steroid doses are reduced, insulin or sulfonylurea doses that were raised to cover the steroid may need reducing in step "
    "to avoid hypoglycemia. Glucose monitoring should continue after steroids stop. These are clinician decisions.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC10037401/")
add("steroid", "Prednisone peaks hours later; dexamethasone lasts longer",
    "Diabetes In Control (primary-care article)", "2026", "clinical-news",
    "Prednisone typically peaks about four to eight hours after a dose, while dexamethasone can raise glucose for much of a day. "
    "Fasting glucose may stay near normal, which can delay recognition. HbA1c can underestimate new steroid-related highs because "
    "they develop over days.",
    "https://www.diabetesincontrol.com/steroid-induced-diabetes-glucose-spikes/")
add("steroid", "Steroid peak times by drug",
    "Corticosteroid-induced hyperglycemia (Research, Society and Development)", "2024", "review",
    "Prednisone and methylprednisolone peak at roughly 4 to 6 hours; dexamethasone can act for up to 24 hours. Steroids impair "
    "glucose uptake in muscle, which mostly hurts the period after meals.",
    "https://rsdjournal.org/rsd/article/download/44900/35868/468942")
add("steroid", "Mealtime insulin needs rise on steroids",
    "University Hospitals (clinician article)", "2024", "clinical-news",
    "Steroids produce large post-meal rises, and some patients need far more mealtime coverage than basal. People who are new to "
    "insulin often need frequent dose changes as the steroid dose changes, with close follow-up.",
    "https://www.uhhospitals.org/for-clinicians/articles-and-news/articles/2024/03/best-practices-for-managing-steroid-induced-hyperglycemia")

# ---------------------------------------------------------------- GLP-1
add("glp1", "GLP-1 drugs lower post-meal glucose largely by slowing stomach emptying",
    "J Clin Endocrinol Metab review", "2025", "review",
    "Slower gastric emptying is a major way GLP-1 receptor agonists and tirzepatide reduce post-meal glucose, and the slowing is "
    "dose-dependent. For long-acting agents the slowing appears to fade over time (tachyphylaxis).",
    "https://academic.oup.com/jcem/article/110/1/1/7824836")
add("glp1", "Weekly GLP-1 effect on emptying is largest after the first doses",
    "FDA clinical pharmacology review of tirzepatide", "2021", "regulatory",
    "Tirzepatide delayed gastric emptying, most after the first dose, with the delay less evident after repeated doses.",
    "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2022/215866Orig1s000ClinPharmR.pdf")
add("glp1", "Emptying delay fades over weeks of GLP-1 treatment",
    "British Journal of Anaesthesia review", "2024", "review",
    "GLP-1 therapy delays stomach emptying most in the first hours after eating and at the start of treatment. The effect subsides "
    "with ongoing treatment, and after roughly 8 to 12 weeks most studies see emptying return toward normal.",
    "https://www.bjanaesthesia.org.uk/article/S0007-0912(24)00002-3/fulltext")
add("glp1", "GLP-1 plus insulin or sulfonylurea: hypoglycemia risk",
    "Endocrinology review of GLP-1-based therapies and gut motility", "2025", "review",
    "Slower emptying lowers post-meal glucose but may carry a risk of hypoglycemia in people who also take insulin or a sulfonylurea.",
    "https://academic.oup.com/endo/article/166/1/bqae155/7906037")

# ---------------------------------------------------------------- food order, activity, sleep
add("meal-order", "Carbohydrates last: lower post-meal peaks in type 2 diabetes",
    "Diabetes Care (crossover trial with CGM)", "2025", "RCT-crossover",
    "In 20 adults with metformin-treated type 2 diabetes, eating fibrous vegetables and protein about 10 minutes before "
    "carbohydrates reduced post-meal glucose peaks and variability for up to 3 hours versus the reverse order, and improved time in range.",
    "https://diabetesjournals.org/care/article/48/2/e15/157633/Carbohydrates-Last-Food-Order-Improves-Time-in")
add("meal-order", "Protein and vegetables first: about 45% lower peak in prediabetes",
    "Shukla et al., food order in prediabetes (PMC7398578)", "2019", "RCT-crossover",
    "Fifteen adults with prediabetes ate the same meal in three orders. Protein and vegetables before carbohydrate cut the incremental "
    "glucose peak by roughly 45% versus carbohydrate first, and vegetables first gave a similar reduction.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC7398578/")
add("meal-order", "Meal sequence in healthy adults: systematic review",
    "Clinical Nutrition Research systematic review", "2026", "systematic-review",
    "Most of six small studies found lower post-meal glucose when vegetables, fruit or protein were eaten before carbohydrate. "
    "The authors call for larger, longer trials, and the effect sizes varied.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC13007804/")
add("sleep", "A week of short sleep lowers insulin sensitivity",
    "Buxton et al., Diabetes (inpatient study of 20 healthy men)", "2010", "experimental",
    "After one week of 5 hours in bed per night, insulin sensitivity fell by about 11 to 20% depending on the method used, in healthy "
    "young men. This is evidence about people without diabetes; applying it to a given person is an inference.",
    "https://pubmed.ncbi.nlm.nih.gov/20585000/")
add("sleep", "Sleep loss, circadian disruption and glucose metabolism",
    "Diabetes in America, chapter 25 (NIDDK)", "2016", "review",
    "Insufficient or fragmented sleep is linked to abnormal glucose metabolism, insulin sensitivity reductions on the order of 20 to 30%, "
    "and higher diabetes risk. Controlled laboratory studies suggest the effect is real but its mechanisms are still being worked out.",
    "https://www.niddk.nih.gov/-/media/Files/Strategic-Plans/Diabetes-in-America-3rd-Edition/DIA_Ch25.pdf")

# ---------------------------------------------------------------- CGM
add("cgm-artifact", "Compression lows: how to recognize them",
    "University of Michigan Depression Center data-cleaning note", "n.d.", "methods-note",
    "A fast, sudden drop from otherwise steady glucose, without exercise or fast-acting insulin, points to a compression low. "
    "Reactive hypoglycemia looks different (fast rise, high peak, fast fall). Confirmed compression lows should be left out of averages, "
    "minimums and standard deviation, but not out of wear time.",
    "https://teamdynamix.umich.edu/TDClient/210/DepressionCenter/KB/Article/10689/CGM-Is-Reading-Low-Values-at-Night-Causes-and-Solutions")
add("cgm-artifact", "Compression lows: timing, duration and verification",
    "CGM white paper (BUZUD)", "2025", "white-paper",
    "Compression lows mostly occur at night and in one cited Dexcom study lasted about 45 minutes (30 to 70). The paper advises "
    "confirming a suspicious CGM low with a fingerstick before treating it with carbohydrates. It is an industry document, so weigh it accordingly.",
    "https://help.buzud.com/v2/product/cgm-system/article/mechanism-analysis-and-clinical-recommendations-for-compression-induced-false-hypoglycemia-in-cgm/")
add("cgm-artifact", "Compression low pattern and recheck routine",
    "Type Strong (consumer article)", "2026", "consumer-health",
    "A compression low usually looks like a sharp drop followed by an equally sharp recovery after pressure is released. "
    "Suggested routine: shift off the sensor, wait 10 to 15 minutes, then recheck the trend.",
    "https://www.type-strong.com/en-us/blogs/all-things-type-1/can-you-sleep-with-a-cgm-patch-on-comfort-wear-tips")
add("cgm-accuracy", "CGM lag and early-wear accuracy",
    "Ubie doctor's note (consumer article)", "2026", "consumer-health",
    "CGMs measure interstitial fluid, which lags blood glucose by roughly 5 to 15 minutes, and the first 12 to 24 hours of a new sensor "
    "can be less accurate. If a reading does not match symptoms, confirm it with a fingerstick.",
    "https://ubiehealth.com/doctors-note/freestyle-libre-3-inaccurate-glucose-tips-steps-42")
add("cgm-accuracy", "Do not over-interpret isolated CGM values",
    "Medscape news report on OTC CGM", "2026", "news",
    "The FDA cautions that users and caregivers should consult a provider before changing medicines based on device output. An "
    "endocrinology expert advises against over-interpreting isolated values, since not every excursion is clinically meaningful.",
    "https://www.medscape.com/viewarticle/continuous-glucose-monitor-adds-ai-features-expands-2026a1000mik")
add("cgm-metrics", "International consensus on CGM targets",
    "Battelino et al., Diabetes Care", "2019", "consensus",
    "The consensus range is 70 to 180 mg/dL. Most adults with type 1 or type 2 diabetes aim for at least 70% time in range, under 4% "
    "below 70 mg/dL, under 1% below 54 mg/dL, under 25% above 180 and under 5% above 250. Targets are personalized, and lower variability "
    "(CV under about 33%) may protect people on insulin or sulfonylureas from lows.",
    "https://diabetesjournals.org/care/article/42/8/1593/36184/Clinical-Targets-for-Continuous-Glucose-Monitoring")
add("cgm-metrics", "Time in range and retinopathy",
    "Battelino et al., Diabetes Care", "2019", "consensus",
    "Analyses of trial data linked each 10% reduction in time in range to a 64% higher hazard of retinopathy progression, and people "
    "with more advanced retinopathy spent less time in range. These are associations, not proof of cause.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC6973648/")

# ---------------------------------------------------------------- pen technique
add("pen", "Two needle caps: remove the outer cap, then the inner cap",
    "Memorial Sloan Kettering patient education", "n.d.", "patient-education",
    "After attaching a pen needle, take off the outer needle cap, then the inner needle cap and throw the inner one away. Do a safety "
    "test before every injection: dial 2 units, point the needle up, press the button, and look for insulin at the tip. If none appears "
    "repeat; if still none after three tries, change the needle. After the safety test the dial should return to zero, then dial the dose. "
    "If the pen will not dial the full dose, it is nearly empty.",
    "https://www.mskcc.org/cancer-care/patient-education/how-use-insulin-pen")
add("pen", "Safety test details: tap, press, confirm insulin comes out",
    "Northwell Health patient handout", "2023", "patient-education",
    "Dial two units, hold the pen needle-up, tap the reservoir to move air toward the needle, press the button fully, and make sure insulin "
    "comes out of the tip. Repeat if not; after three failed tries replace the needle. Confirm the dose window reads zero before dialing the dose.",
    "https://www.northwell.edu/sites/northwell.edu/files/2023-10/how-to-use-insulin-pen.pdf")
add("pen", "Keep the outer cap, hold the button, roll cloudy insulin",
    "Kaiser Permanente patient education", "n.d.", "patient-education",
    "Remove the outer cap and keep it for removing the needle later, then remove the inner cover. After pressing the button, hold it in "
    "for 10 seconds or the time the manufacturer recommends before pulling the needle out. Put only the outer cap back on to unscrew the "
    "needle. Cloudy insulins such as NPH and premixed are gently rolled between the palms about 10 times before use. Opened pens generally expire within about a month.",
    "https://healthy.kaiserpermanente.org/health-wellness/health-encyclopedia/he.learning-about-how-to-use-an-insulin-pen.acd5618")
add("pen", "Manufacturer guidance for a prefilled glargine pen",
    "Lantus SoloStar how-to-inject page (manufacturer)", "n.d.", "manufacturer",
    "The safety-test step includes taking off the outer needle cap (keep it) and the inner needle cap (discard). After injecting, count "
    "slowly to 10 before withdrawing the needle so the full dose is delivered. Remove the needle after each dose and store the pen without "
    "a needle attached, because a stored needle can allow leaks and air that make dosing inaccurate.",
    "https://www.lantus.com/how-to-use/how-to-inject")
add("pen", "Label: prime every time, needle fully attached",
    "FDA-hosted label with pen instructions for use (older NPH pen label)", "2005", "regulatory",
    "The instructions warn that not following the steps can deliver too much or too little insulin: use a new needle each time, be sure "
    "the needle is fully attached before priming, and prime before every injection to confirm insulin comes out and to clear air. "
    "Do not store the pen with the needle attached. The label also carries a statement discouraging use by blind or visually impaired "
    "people (the excerpt I read was cut off; read the full label).",
    "https://www.accessdata.fda.gov/drugsatfda_docs/label/2005/018781s025,060,065,085lbl.pdf")
add("pen", "Needle hold time differs by pen",
    "Cleveland Clinic patient education", "2026", "consumer-health",
    "Sources differ on how long to hold the needle in the skin (about 6 to 10 seconds here, 10 seconds on a manufacturer page), so use "
    "the time in the instructions for the specific pen.",
    "https://my.clevelandclinic.org/health/treatments/17923-insulin-pen-injections")

# ---------------------------------------------------------------- injection sites
add("site", "Where to inject: belly, thighs, arms, buttocks; rotate within one area",
    "University of Iowa Health Care patient education", "2017", "patient-education",
    "Insulin goes into the fatty layer of the belly (staying two inches from the belly button; it absorbs fastest there), the top and "
    "outer thigh between a hand-width below the groin and a hand-width above the knee (not the inner thigh), the outer back of the upper "
    "arm, or the upper outer buttock. Choose one body area and keep using it, but change the exact spot within that area each time. "
    "Do not inject into scars, bruises or sores.",
    "https://uihc.org/educational-resources/injecting-insulin")
add("site", "Navel distance, scars, sore or lumpy spots",
    "MedlinePlus (US National Library of Medicine)", "n.d.", "patient-education",
    "Keep injections about 2 inches (5 cm) from the navel and 1 inch (2.5 cm) from scars. Keep a chart of the spots used so the same place "
    "is not used every time. Avoid spots that are bruised, swollen or tender, and spots that are lumpy, firm or numb, which the page calls "
    "a very common cause of insulin not working. Guidance on skin cleaning and needle angle differs between sources: follow the "
    "instructions for your own pen and needle.",
    "https://medlineplus.gov/ency/patientinstructions/000660.htm")
add("site", "Lumps from injecting in the same spot (lipohypertrophy)",
    "Cleveland Clinic patient education", "n.d.", "consumer-health",
    "Injecting into the same spot again and again can build a firm, rubbery or numb lump of fatty tissue, most often on the belly or thigh. "
    "Insulin injected into it may be absorbed more slowly or faster than expected, causing highs or lows. Prevention: change the spot "
    "every time, at least one finger-width from the last, use a new needle each time, keep a chart, and check the skin before injecting. "
    "If a lump is found, avoid that area for at least two to three months and ask the care team to check it.",
    "https://my.clevelandclinic.org/health/diseases/22928-lipohypertrophy")

# ---------------------------------------------------------------- one passage per insulin pen (from pen_data, each from its IFU)
from .pens import ALL as _PENS, passage as _passage  # noqa: E402
for _p in _PENS:
    add(**{k if k != "evidence_level" else "level": v for k, v in _passage(_p).items()})

# ---------------------------------------------------------------- accessibility
add("accessibility", "Visual impairment and insulin pens: prevalence and disclaimers",
    "Williams & Schnarrenberger, J Diabetes Sci Technol", "2010", "pilot-study",
    "About 18% of people with diagnosed diabetes in the US have visual impairment. Major manufacturers' pen instructions warn against use "
    "by visually impaired people without giving a reason. In a small dosing-accuracy study, blind and sighted participants dosed comparably, "
    "but the authors say more study is needed.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC2901026/")
add("accessibility", "Which pen steps need sight, and workarounds",
    "AccessWorld (American Foundation for the Blind)", "n.d.", "accessibility-review",
    "Mixing insulin and reading the cartridge gauge to confirm enough insulin remains cannot be done without sufficient vision. Audible "
    "clicks as the dial passes each number help confirm the dose. One workaround is to keep a running total of units used. Diagrams in the "
    "pen manuals were not accessible to screen readers and none came in braille.",
    "https://afb.org/aw/7/4/14552")
add("accessibility", "Audible clicks help, but technique errors are common",
    "Pen preference and dexterity analysis (PMC3440164)", "2012", "review",
    "Audible dose clicks may help people with low vision dial accurately, though manufacturers discourage solo use without sighted "
    "assistance. In a mock-injection study, more than a third of patients made technique errors with both pens tested.",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC3440164/")
add("accessibility", "Click clarity differs between pens",
    "Assessment of audible dose-setting confirmation (PubMed 16120036)", "2005", "RCT",
    "In a randomized study of 48 patients, significantly more detected the dose-setting click on some pen models than on others, so a "
    "person with low vision should choose a pen whose click they can clearly hear.",
    "https://pubmed.ncbi.nlm.nih.gov/16120036/")
add("accessibility", "Voice features of CGM are under-used",
    "Provider survey on diabetes technology for visually impaired patients", "n.d.", "survey",
    "In a survey of 66 US providers, 96% recommended CGM for visually impaired patients but only 55% knew about the Dexcom G6 voice "
    "announcements. Spoken glucose values and audible alerts were major reasons to choose CGM.",
    "https://www.researchgate.net/publication/44640468_A_Comparison_of_Dosing_Accuracy_Visually_Impaired_and_Sighted_People_Using_Insulin_Pens")
add("accessibility", "Aids for low vision: talking meters and other tools",
    "Medscape Education: Insulin and Visually Impaired Patients", "n.d.", "clinical-education",
    "Options include talking glucose meters, count-a-dose devices for syringes, pens that click with each unit, and pharmacist-prefilled "
    "syringes stored in the refrigerator. Meters with a larger display or a synthetic voice can help with testing.",
    "https://www.medscape.org/viewarticle/581168")
