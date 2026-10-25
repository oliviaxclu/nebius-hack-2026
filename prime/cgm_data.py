"""CGM sensor profiles: the spoken sensor-application check follows the person's own sensor. See cgm.py for how they are used.

Every step below is paraphrased from the sources listed with that sensor (manufacturer instructions, read on `checked`).
Nothing here is a dose or a glucose reading: profiles only describe how to put the device on. Re-check against the
instructions in your own sensor box before relying on this beyond a demo.

coverage "full"    every step comes from a published source.
coverage "limited" the sensor is placed by a clinician (Eversense), or no published insertion steps were found
                   (Guardian 4, "other"), so Prime checks only the kit, the skin prep and the finished patch and says so (`caveat`).
`check` names a camera checkpoint in cgm_vision.py. `{site}` in a spoken step is replaced with today's rotation spot.
"""

FIELDS = ("id", "name", "maker", "coverage", "keyword", "sites", "steps", "after", "caveat", "sources", "checked")
CHECKS = ("kit", "site", "cap", "labels", "applied", "patch", "transmitter")

CGMS: list[dict] = [{'id': 'dexcom-g7',
  'name': 'Dexcom G7 / G7 15 Day',
  'maker': 'Dexcom',
  'coverage': 'full',
  'keyword': 'Dexcom',
  'sites': ['back of left upper arm', 'back of right upper arm'],
  'steps': [{'check': 'kit', 'say': 'Show me the Dexcom G7 / G7 15 Day sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Wash and dry your hands. Clean the back of your upper arm with an alcohol swab and let it dry. Avoid spots you lie on or that '
                    'get bumped, and spots within three inches of an injection site. {site} Show me the bare skin and say done.'},
            {'check': 'cap', 'say': "Unscrew the cap from the applicator and don't touch inside it. Show me the applicator and say done."},
            {'check': 'applied',
             'say': 'Press and hold the applicator firmly against your skin and relax your arm. Push the button, then remove the applicator. Show me '
                    'and say done.'},
            {'check': 'patch',
             'say': 'Rub firmly around the sticky patch three times, then press gently on the sensor for ten seconds. Use the overpatch from your '
                    'kit if it needs extra hold. Show me the patch and say done.'}],
  'after': 'Next, open the Dexcom app and follow its pairing steps. The sensor needs about an hour to warm up. Keep the applicator, you may need its '
           'pairing code.',
  'caveat': None,
  'sources': [('Dexcom: how to insert the G7 or G7 15 Day sensor',
               'https://provider.dexcom.com/clinical-education-material/how-insert-dexcom-g7-or-dexcom-15-day-sensor')],
  'checked': '2026-10-25'},
 {'id': 'dexcom-g6',
  'name': 'Dexcom G6',
  'maker': 'Dexcom',
  'coverage': 'full',
  'keyword': 'Dexcom',
  'sites': [],
  'steps': [{'check': 'kit', 'say': 'Show me the Dexcom G6 sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Wash and dry your hands. Pick a site at least three inches from your pump or injection site, away from bony areas, scars, '
                    'tattoos, thick hair or irritated skin. {site} Clean it with rubbing alcohol and let it dry. Show me the bare skin and say '
                    'done.'},
            {'check': 'labels', 'say': 'Peel both labels off the applicator without touching the sticky side. Show me the applicator and say done.'},
            {'check': 'applied',
             'say': 'Press the sticky side of the applicator onto the cleaned skin. Fold and break off the orange safety guard, press the button, '
                    'then pull the applicator away. Show me and say done.'},
            {'check': 'transmitter',
             'say': 'Slide the transmitter tab into the slot on the sensor holder and snap it firmly into place. Show me and say done.'},
            {'check': 'patch', 'say': 'Check that the patch and the transmitter sit flat on the skin. Show me and say done.'}],
  'after': 'Next, pair the transmitter with your app or receiver as your Dexcom G6 guide shows.',
  'caveat': None,
  'sources': [('Dexcom: inserting the G6 sensor and attaching the transmitter',
               'https://www.dexcom.com/en-us/training-videos/inserting-sensor-and-attaching-transmitter'),
              ('Dexcom FAQ: how do I insert my G6 sensor', 'https://www.dexcom.com/en-GB/faqs/how-do-i-insert-my-dexcom-g6-sensor')],
  'checked': '2026-10-25'},
 {'id': 'dexcom-stelo',
  'name': 'Dexcom Stelo',
  'maker': 'Dexcom',
  'coverage': 'full',
  'keyword': 'Stelo',
  'sites': ['back of left upper arm', 'back of right upper arm'],
  'steps': [{'check': 'kit', 'say': 'Show me the Dexcom Stelo sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Wash and dry your hands. Choose the back of your upper arm, away from spots that get bumped or that you lie on. Clean it with '
                    'the alcohol swab and let it dry for at least ten seconds. {site} Show me the bare skin and say done.'},
            {'check': 'applied',
             'say': 'Press and hold the applicator firmly against your skin until the clear safety guard is pushed in. Then push the button on the '
                    'side. You should feel a click. Show me and say done.'},
            {'check': 'patch', 'say': 'Put the overpatch from your kit over the sensor. Show me the patch and say done.'}],
  'after': 'Next, follow the in-app guide in the Stelo app to connect your sensor. Take a photo of the serial number on the applicator in case you '
           'need support.',
  'caveat': None,
  'sources': [('Stelo: how do I insert my sensor and apply the overpatch',
               'https://www.stelo.com/en-us/faqs/using-stelo/how-do-i-insert-my-sensor-and-apply-the-overpatch')],
  'checked': '2026-10-25'},
 {'id': 'libre-2-plus',
  'name': 'FreeStyle Libre 2 Plus',
  'maker': 'Abbott',
  'coverage': 'full',
  'keyword': 'FreeStyle Libre',
  'sites': ['back of left upper arm', 'back of right upper arm'],
  'steps': [{'check': 'kit', 'say': 'Show me the FreeStyle Libre 2 Plus sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Choose a spot on the back of your upper arm that stays flat during normal activity, with no scars, moles, stretch marks or '
                    'swelling. Skip body lotion there. Wash with fragrance-free soap and water, wipe with alcohol, and let it air dry. Do not blow '
                    'on it. {site} Show me the bare skin and say done.'},
            {'check': 'cap',
             'say': 'Take the lid off the sensor pack and unscrew the applicator cap. Line up the dark mark on the applicator with the dark mark on '
                    'the pack, press down firmly on a hard surface until it stops, then lift it out. Show me and say done.'},
            {'check': 'applied',
             'say': 'Place the applicator over the back of your upper arm and press firmly until you hear a click. Wait a few seconds, then pull it '
                    'back slowly. Do not put the cap back on. Show me and say done.'},
            {'check': 'patch', 'say': 'Press gently with a finger around the edge of the sensor to secure it. Show me the sensor and say done.'}],
  'after': 'Next, open the Libre app and scan the new sensor. It can be used after a 60 minute start-up.',
  'caveat': None,
  'sources': [('Abbott: how to get started with your FreeStyle Libre system', 'https://www.freestyle.abbott/uk-en/support/firstuse.html'),
              ('Abbott guided support: sensor answers',
               'https://pro.freestyle.abbott/uk-en/libre-hub/guided-support-question-flow/A10-hcp-sensor-answers.html')],
  'checked': '2026-10-25'},
 {'id': 'libre-3',
  'name': 'FreeStyle Libre 3 / 3 Plus',
  'maker': 'Abbott',
  'coverage': 'full',
  'keyword': 'FreeStyle Libre',
  'sites': ['back of left upper arm', 'back of right upper arm'],
  'steps': [{'check': 'kit', 'say': 'Show me the FreeStyle Libre 3 / 3 Plus sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Choose a spot on the back of your upper arm that stays flat during normal activity, with no scars, moles, stretch marks or '
                    'swelling. Skip body lotion there. Wash with fragrance-free soap and water, wipe with alcohol, and let it air dry. Do not blow '
                    'on it. {site} Show me the bare skin and say done.'},
            {'check': 'cap', 'say': 'Unscrew the cap from the applicator. Do not put the cap back on. Show me the applicator and say done.'},
            {'check': 'applied',
             'say': 'Place the applicator over the back of your upper arm and press firmly until you hear a click. Wait a few seconds, then pull '
                    'back slowly, leaving the sensor on your skin. Show me and say done.'},
            {'check': 'patch', 'say': 'Check that the sensor is stuck down all the way around. Show me and say done.'}],
  'after': 'Next, start the sensor in the Libre app. It sends readings to your phone, so you do not need to scan it.',
  'caveat': None,
  'sources': [('Abbott: how to apply and remove the FreeStyle Libre 3 Plus sensor',
               'https://www.freestyle.abbott/en-us/support/faq/sensor/how-to-apply-and-remove-the-freestyle-libre-3-plus-sensor.html'),
              ('Abbott: how to get started with your FreeStyle Libre system', 'https://www.freestyle.abbott/uk-en/support/firstuse.html')],
  'checked': '2026-10-25'},
 {'id': 'lingo',
  'name': 'Abbott Lingo biosensor',
  'maker': 'Abbott',
  'coverage': 'full',
  'keyword': 'Lingo',
  'sites': ['back of left upper arm', 'back of right upper arm'],
  'steps': [{'check': 'kit', 'say': 'Show me the Abbott Lingo biosensor sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Use only the back of your upper arm, away from scars, moles, stretch marks or lumps, on skin that stays flat during the day. '
                    'Wash with plain soap, dry, wipe with alcohol and let it air dry fully. {site} Show me the bare skin and say done.'},
            {'check': 'cap',
             'say': 'Open the pack and unscrew the applicator cap. Line up the dark marks on the applicator and the pack, and press the applicator '
                    "down on a flat, hard surface until it stops. Lift it out. It now holds a needle, so don't touch inside. Show me and say done."},
            {'check': 'applied',
             'say': 'Place the applicator over your prepared skin, push down firmly, then pull it straight away. Show me and say done.'},
            {'check': 'patch', 'say': 'Check that the sensor is secure and flat. Show me and say done.'}],
  'after': 'Next, open the Lingo app and hold your phone against the sensor until pairing is confirmed. The adhesive keeps settling for the first '
           'twelve hours.',
  'caveat': None,
  'sources': [('Lingo: how do I apply and activate my biosensor',
               'https://support.hellolingo.com/hc/en-us/articles/12235073435287-How-do-I-apply-and-activate-my-biosensor')],
  'checked': '2026-10-25'},
 {'id': 'simplera-sync',
  'name': 'Medtronic Simplera Sync',
  'maker': 'Medtronic',
  'coverage': 'full',
  'keyword': 'Simplera',
  'sites': ['back of left upper arm', 'back of right upper arm'],
  'steps': [{'check': 'kit', 'say': 'Show me the Medtronic Simplera Sync sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Use only the back of your upper arm, at least one inch from any pump or injection site. Clean it with an alcohol wipe and let '
                    'it dry fully. {site} Show me the bare skin and say done.'},
            {'check': 'cap', 'say': 'Take the cap off the inserter. Show me the inserter and say done.'},
            {'check': 'applied',
             'say': 'Press the inserter firmly against your skin until it clicks, with one smooth, firm, continuous push. Show me and say done.'},
            {'check': 'patch',
             'say': 'Smooth the adhesive down with a finger. Use overtape only if you are very active or it is hot and humid. Show me the sensor and '
                    'say done.'}],
  'after': 'Next, pair the sensor on your pump within twenty minutes of removing the cap. A few spots of light bleeding can be normal, but if it '
           'keeps going, follow your sensor guide.',
  'caveat': None,
  'sources': [('Medtronic: Simplera Sync sensor support', 'https://www.minimed.com/en-us/support/product-support/sensors/simplera-sync'),
              ('Medtronic: Simplera Sync sensor instructions for use',
               'https://origin.medtronicdiabetes.com/sites/default/files/library/download-library/user-guides/Simplera-Sync-Sensor-IFU.pdf')],
  'checked': '2026-10-25'},
 {'id': 'guardian-4',
  'name': 'Medtronic Guardian 4',
  'maker': 'Medtronic',
  'coverage': 'limited',
  'keyword': 'Guardian',
  'sites': [],
  'steps': [{'check': 'kit', 'say': 'Show me the Medtronic Guardian 4 sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Wash and dry your hands. Clean the skin with an alcohol swab and let it dry fully. {site} Show me the bare skin and say done.'},
            {'check': 'patch',
             'say': 'Insert the sensor as your Guardian 4 guide shows. Then check that the patch is stuck flat all the way around. Show me and say '
                    'done.'}],
  'after': 'Next, finish pairing as your Guardian 4 guide shows.',
  'caveat': 'I could not confirm the Guardian 4 insertion steps from published sources, so for this model I only check the kit, the skin prep and '
            'the finished patch. Do the insertion itself from the guide in your box.',
  'sources': [],
  'checked': '2026-10-25'},
 {'id': 'eversense-365',
  'name': 'Eversense 365',
  'maker': 'Senseonics',
  'coverage': 'limited',
  'keyword': 'Eversense',
  'sites': [],
  'steps': [{'check': 'kit', 'say': 'Show me the Eversense 365 sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Remove any lotion or soap from the skin over your sensor, and let the skin dry completely. Show me the bare, dry skin and say '
                    'done.'},
            {'check': 'applied',
             'say': 'Place the adhesive patch and smart transmitter over your sensor as your Eversense guide shows. Show me and say done.'},
            {'check': 'patch', 'say': 'Check that the patch and transmitter are stuck flat with no lifted edges. Show me and say done.'}],
  'after': 'Your adhesive patch is changed on a schedule set by Eversense, so follow your guide.',
  'caveat': 'The Eversense sensor is placed under your skin by a healthcare provider, so there is no sensor to apply yourself. This guide only '
            'covers skin prep and checking the adhesive patch and smart transmitter that sit over it.',
  'sources': [('Eversense 365 adhesive options',
               'https://eversensecgm.com/siteassets/eversense-pwd-resources/eversense-365_adhesivesoptions_102224_v2.pdf'),
              ('Eversense 365', 'https://eversensecgm.com/eversense-365')],
  'checked': '2026-10-25'},
 {'id': 'other',
  'name': 'Another CGM (not listed)',
  'maker': 'Other',
  'coverage': 'limited',
  'keyword': '',
  'sites': [],
  'steps': [{'check': 'kit', 'say': 'Show me the Another CGM (not listed) sensor kit or applicator and its packaging, then say done.'},
            {'check': 'site',
             'say': 'Wash and dry your hands. Clean the skin with an alcohol swab and let it air dry fully. Use the site your guide recommends. '
                    '{site} Show me the bare skin and say done.'},
            {'check': 'patch',
             'say': 'Apply the sensor as your guide shows. Then check that the patch is stuck flat all the way around. Show me and say done.'}],
  'after': 'Finish setup as the guide in your box describes.',
  'caveat': "I do not have this model's steps. I can help check the kit, the skin prep and the finished patch. Do the sensor insertion from the "
            'guide in your box.',
  'sources': [],
  'checked': '2026-10-25'}]

for _c in CGMS:                                    # every profile has every field; limited ones must say what they cannot do
    assert set(_c) == set(FIELDS), (_c["id"], set(FIELDS) ^ set(_c))
    assert all(s["check"] in CHECKS for s in _c["steps"]), _c["id"]
    assert _c["coverage"] == "full" or _c["caveat"], _c["id"]
