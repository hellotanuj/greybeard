"""Generate Greybeard's synthetic-but-realistic service history.

Output (written to ./data):
  sites.json         5 commercial sites across Hyderabad's IT corridor
  technicians.json   field technicians, from a 22-year veteran to an 8-month junior
  assets.json        ~24 pieces of plant equipment (chillers, DG sets, lifts, UPS, AHUs)
  history.json       ~18 months of closed work orders (narrative "story" jobs + routine PMs)
  open_tickets.json  today's dispatch board, used for the live demo

The narrative jobs deliberately encode the kind of tribal knowledge that normally
lives only in a senior technician's head: recurring root causes, fixes that did NOT
work, equipment-batch defects, seasonal patterns and site access quirks. Routine PMs
add realistic noise so recall has to actually find the signal.

Deterministic: same seed -> same data.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(1729)
OUT = Path(__file__).resolve().parent.parent / "data"

# ----------------------------------------------------------------------------- sites
SITES = [
    {
        "id": "orbit",
        "name": "Orbit Towers",
        "locality": "Nanakramguda, Financial District",
        "facility_manager": "Sudhakar Rao",
        "notes": [
            "Terrace plant room access needs a security escort; the terrace key is held by FM Sudhakar Rao.",
            "Work permits must be raised before 9:00 AM or the job slips to the next day.",
            "No hot work (brazing/welding) on Fridays: the anchor tenant runs weekly compliance audits.",
            "Adjacent plot has had active construction since early 2025, so condenser coils load up with dust fast.",
        ],
    },
    {
        "id": "sapphire",
        "name": "Sapphire Square",
        "locality": "Raidurg",
        "facility_manager": "Mahesh Chary",
        "notes": [
            "DG yard is in the lower basement (B2) and takes on water during heavy monsoon rain; carry gumboots Jul-Sep.",
            "DG load tests only allowed 6:00-8:00 AM on weekdays (tenant UPS sync issues otherwise).",
        ],
    },
    {
        "id": "meridian",
        "name": "Meridian IT SEZ",
        "locality": "Kondapur",
        "facility_manager": "Anitha Joseph",
        "notes": [
            "SEZ gate pass needs the laptop serial number and must be registered a day in advance; walk-in gate pass takes ~40 minutes.",
            "Tower B food court is on level 3; catering carts drag debris into lift sills on floors 2-4.",
        ],
    },
    {
        "id": "lakeside",
        "name": "Lakeside One",
        "locality": "Gachibowli",
        "facility_manager": "Farah Siddiqui",
        "notes": [
            "FM Farah Siddiqui expects WhatsApp photo updates every 30 minutes during any outage.",
            "A written root-cause note is expected within 24 hours of every chiller trip.",
        ],
    },
    {
        "id": "helix",
        "name": "Helix Park",
        "locality": "Madhapur",
        "facility_manager": "Pradeep Menon",
        "notes": [
            "UPS room on level 1 has a single split AC with no redundancy.",
            "New chiller CH-04 commissioned August 2026 to support tenant expansion.",
        ],
    },
]

TECHS = [
    {"id": "ravi", "name": "Ravi Kumar Goud", "years": 22, "role": "Senior Chiller & DG Specialist", "note": "Retiring in December 2026."},
    {"id": "srinivas", "name": "Srinivas Reddy", "years": 11, "role": "HVAC Technician"},
    {"id": "imran", "name": "Imran Shaikh", "years": 7, "role": "Lift & Electrical Technician"},
    {"id": "lakshmi", "name": "Lakshmi Prasanna", "years": 5, "role": "Electrical / UPS Technician"},
    {"id": "arjun", "name": "Arjun Varma", "years": 0.7, "role": "Junior Field Technician"},
]
TECH_NAME = {t["id"]: t["name"] for t in TECHS}

# ----------------------------------------------------------------------------- assets
ASSETS = [
    # Chillers: Kryo ACX-500 air-cooled screw, R-134a
    {"id": "ORB-CH-01", "site": "orbit", "type": "chiller", "model": "Kryo ACX-500", "serial": "KX-2011-0412", "installed": "2020-11", "desc": "500 TR air-cooled screw chiller, R-134a, 2 circuits, 4 condenser fan banks on VFDs"},
    {"id": "ORB-CH-02", "site": "orbit", "type": "chiller", "model": "Kryo ACX-500", "serial": "KX-2011-0413", "installed": "2020-11", "desc": "500 TR air-cooled screw chiller, R-134a, 2 circuits, 4 condenser fan banks on VFDs"},
    {"id": "ORB-CH-03", "site": "orbit", "type": "chiller", "model": "Kryo ACX-500", "serial": "KX-2203-0877", "installed": "2022-03", "desc": "500 TR air-cooled screw chiller, standby unit"},
    {"id": "LAK-CH-01", "site": "lakeside", "type": "chiller", "model": "Kryo ACX-500", "serial": "KX-1908-0233", "installed": "2019-08", "desc": "500 TR air-cooled screw chiller, R-134a"},
    {"id": "LAK-CH-02", "site": "lakeside", "type": "chiller", "model": "Kryo ACX-500", "serial": "KX-1908-0234", "installed": "2019-08", "desc": "500 TR air-cooled screw chiller, R-134a"},
    {"id": "HLX-CH-01", "site": "helix", "type": "chiller", "model": "Kryo ACX-350", "serial": "KX-1905-0101", "installed": "2019-05", "desc": "350 TR air-cooled screw chiller"},
    {"id": "HLX-CH-02", "site": "helix", "type": "chiller", "model": "Kryo ACX-350", "serial": "KX-1905-0102", "installed": "2019-05", "desc": "350 TR air-cooled screw chiller"},
    {"id": "HLX-CH-04", "site": "helix", "type": "chiller", "model": "Kryo ACX-500", "serial": "KX-2607-1190", "installed": "2026-08", "desc": "500 TR air-cooled screw chiller, commissioned Aug 2026, condenser fans on factory-fitted Kryo SD-40 sealed drives, no service history yet"},
    # DG sets
    {"id": "SAP-DG-01", "site": "sapphire", "type": "dg_set", "model": "Voltara VG-750", "serial": "VG750-17-221", "installed": "2017-06", "desc": "750 kVA diesel generator, 24V electric start, basement B2 yard"},
    {"id": "SAP-DG-02", "site": "sapphire", "type": "dg_set", "model": "Voltara VG-750", "serial": "VG750-17-222", "installed": "2017-06", "desc": "750 kVA diesel generator, 24V electric start, basement B2 yard"},
    {"id": "ORB-DG-01", "site": "orbit", "type": "dg_set", "model": "Voltara VG-1010", "serial": "VG1010-20-045", "installed": "2020-10", "desc": "1010 kVA diesel generator, ground-floor acoustic enclosure"},
    {"id": "MER-DG-01", "site": "meridian", "type": "dg_set", "model": "Voltara VG-750", "serial": "VG750-18-310", "installed": "2018-02", "desc": "750 kVA diesel generator, open yard"},
    # Lifts
    {"id": "MER-LFT-B3", "site": "meridian", "type": "lift", "model": "Liftra MRL-13", "serial": "LM13-18-7781", "installed": "2018-01", "desc": "13-passenger machine-room-less lift, Tower B car 3, serves B1-G+12"},
    {"id": "MER-LFT-B2", "site": "meridian", "type": "lift", "model": "Liftra MRL-13", "serial": "LM13-18-7780", "installed": "2018-01", "desc": "13-passenger MRL lift, Tower B car 2"},
    {"id": "LAK-LFT-01", "site": "lakeside", "type": "lift", "model": "Liftra MRL-16", "serial": "LM16-19-0912", "installed": "2019-08", "desc": "16-passenger MRL lift"},
    # UPS
    {"id": "HLX-UPS-01", "site": "helix", "type": "ups", "model": "Powerline PX-200", "serial": "PX200-21-5521", "installed": "2021-04", "desc": "200 kVA online UPS, 2 x 40-block VRLA battery strings"},
    {"id": "SAP-UPS-01", "site": "sapphire", "type": "ups", "model": "Powerline PX-160", "serial": "PX160-20-3319", "installed": "2020-09", "desc": "160 kVA online UPS"},
    # AHUs
    {"id": "ORB-AHU-07", "site": "orbit", "type": "ahu", "model": "Airnova AH-25", "serial": "AN25-20-1107", "installed": "2020-11", "desc": "25,000 CFM AHU, floor 7"},
    {"id": "LAK-AHU-03", "site": "lakeside", "type": "ahu", "model": "Airnova AH-18", "serial": "AN18-19-0303", "installed": "2019-08", "desc": "18,000 CFM AHU, floor 3"},
    {"id": "MER-AHU-B5", "site": "meridian", "type": "ahu", "model": "Airnova AH-25", "serial": "AN25-18-0505", "installed": "2018-01", "desc": "25,000 CFM AHU, Tower B floor 5"},
    {"id": "HLX-AHU-02", "site": "helix", "type": "ahu", "model": "Airnova AH-18", "serial": "AN18-19-0202", "installed": "2019-05", "desc": "18,000 CFM AHU, floor 2"},
    # Cooling-related pumps
    {"id": "ORB-PMP-02", "site": "orbit", "type": "pump", "model": "Hydrax SP-75", "serial": "HX75-20-0022", "installed": "2020-11", "desc": "Secondary chilled water pump 2, 75 kW on VFD"},
    {"id": "LAK-PMP-01", "site": "lakeside", "type": "pump", "model": "Hydrax SP-55", "serial": "HX55-19-0011", "installed": "2019-08", "desc": "Primary chilled water pump 1"},
]
ASSET = {a["id"]: a for a in ASSETS}

# ----------------------------------------------------------------------------- narrative jobs
# Each tuple: (wo_id, opened "YYYY-MM-DD HH:MM", duration_h, asset, tech, alarm, symptom, notes, root_cause, outcome, parts, downtime_h)
# outcome: fixed | not_fixed | false_alarm | pm | advisory
STORY = [
    # ---- Pattern 1: ORB-CH-02 A-140 high discharge pressure. Coil washes fail; real cause is VFD panel cooling fan.
    ("WO-2504-031", "2025-04-17 14:10", 4.5, "ORB-CH-02", "srinivas", "A-140", "Chiller tripped on high discharge pressure during afternoon peak.",
     "Arrived 14:55. CH-02 locked out on A-140, circuit 2 discharge 1,640 kPa (trip at 1,600). Ambient 41°C. Condenser coils visibly loaded with cement dust from the construction next door. Did a full coil wash with foam cleaner, both circuits. Reset and restarted 18:20, ran stable at 1,380 kPa till 19:30 when I left.",
     "Condenser coil fouling (construction dust)", "fixed", ["Coil cleaner 20L"], 5.0),
    ("WO-2504-058", "2025-04-26 15:05", 5.0, "ORB-CH-02", "srinivas", "A-140", "Repeat A-140 trip, nine days after coil wash.",
     "A-140 again on circuit 2, same time of day. Coils still clean from last week. Topped up nothing, refrigerant charge looks normal on sight glass. Washed coils again to be safe and checked condenser fan motors, all four banks spinning. Restarted 19:40. Could not find a root cause. Flagged for senior review.",
     "Unknown - suspected coil fouling", "not_fixed", ["Coil cleaner 20L"], 6.0),
    ("WO-2505-012", "2025-05-06 14:40", 3.0, "ORB-CH-02", "ravi", "A-140", "Third A-140 trip in three weeks on circuit 2.",
     "Came in with Srinivas. Coils are clean, so it is not the coils. Pulled the fault log on the fan bank 2 VFD: F-07 heatsink over-temperature, 14 events, all between 13:00 and 17:00. VFD was derating fan bank 2 to ~60% speed exactly when head pressure peaks. Opened the VFD panel: panel cooling fan seized, filter choked with dust. Replaced panel fan (PF-120) and filter. Fan bank 2 back to 100% on the hot afternoon. Discharge pressure dropped from 1,590 to 1,310 kPa under the same load. Lesson: on the ACX-500, if A-140 repeats on one circuit and the coils are clean, check that circuit's fan VFD fault log before anything else. Coil washes won't fix it.",
     "Condenser fan VFD derating (F-07 over-temp) caused by seized VFD panel cooling fan", "fixed", ["VFD panel fan PF-120", "Panel filter mat"], 3.5),
    ("WO-2506-044", "2025-06-12 10:00", 1.5, "ORB-CH-01", "ravi", None, "Proactive inspection of VFD panel fans on sister unit.",
     "After the CH-02 finding, checked all four VFD panels on CH-01. Bank 3 panel fan was noisy and running slow, so I replaced it before it seized. Recommend adding VFD panel fans and filters to the pre-summer PM checklist for every ACX-500 at dusty sites.",
     "Preventive: VFD panel fan wear", "advisory", ["VFD panel fan PF-120"], 0.0),
    ("WO-2604-019", "2026-04-09 15:20", 2.0, "ORB-CH-01", "srinivas", "A-140", "A-140 on circuit 1 during 42°C afternoon.",
     "Remembered the CH-02 case from last year. Went straight to the fan VFD logs: bank 1 VFD F-07 events x9. Panel fan OK but the filter was completely blocked with construction dust. Replaced the filter, and the VFD stopped derating. Discharge back to 1,340 kPa. Took 2 hours total instead of a day of coil washing.",
     "Fan VFD derating from blocked panel filter", "fixed", ["Panel filter mat"], 2.0),

    # ---- Pattern 2: Pressure transducer drift on KX-19xx serial batch -> false A-140
    ("WO-2507-066", "2025-07-21 11:30", 5.5, "LAK-CH-01", "srinivas", "A-140", "A-140 trip at moderate ambient (31°C).",
     "Odd one. Trip at only 31°C ambient. Controller showed 1,620 kPa discharge on circuit 1. Coil wash done, fans checked. Restarted, tripped again after 40 minutes. Left the unit locked out overnight for Ravi. FM Farah unhappy with the lack of updates. She wants photos every 30 minutes.",
     "Unknown", "not_fixed", ["Coil cleaner 20L"], 20.0),
    ("WO-2507-071", "2025-07-22 08:10", 2.5, "LAK-CH-01", "ravi", "A-140", "Follow-up on overnight lockout.",
     "Connected a manifold gauge to circuit 1: actual discharge 1,210 kPa, but the controller read 1,610. Discharge pressure transducer drifted ~400 kPa high. Replaced transducer (PT-3000, 0-3,000 kPa). Unit ran all day with no trips. Note: this is a 2019 unit (serial KX-19xx). The 2019 ACX batch used the older transducer revision. If A-140 shows up at low ambient on a KX-19xx serial, put a manifold gauge on it FIRST (10 minutes) before washing anything.",
     "Discharge pressure transducer drift (false high reading), 2019 batch", "false_alarm", ["Pressure transducer PT-3000"], 2.5),
    ("WO-2511-014", "2025-11-08 16:45", 1.0, "HLX-CH-02", "lakshmi", "A-140", "A-140 in November (ambient 27°C).",
     "Low ambient trip, KX-1905 serial. Remembered Ravi's note on 2019 transducers. Gauge read 1,150 kPa vs controller 1,560. Replaced transducer. 1 hour job.",
     "Discharge pressure transducer drift, 2019 batch", "false_alarm", ["Pressure transducer PT-3000"], 1.0),
    ("WO-2602-027", "2026-02-19 09:30", 1.5, "LAK-CH-02", "ravi", None, "Proactive transducer check on remaining 2019-batch unit.",
     "Checked both circuit discharge transducers on LAK-CH-02 against gauge: circuit 2 reading 180 kPa high and climbing. Replaced proactively. Remaining 2019-batch unit not yet checked: HLX-CH-01.",
     "Preventive: transducer drift", "advisory", ["Pressure transducer PT-3000"], 0.0),

    # ---- Pattern 3: Sapphire DG fail-to-start in monsoon. Battery swaps fail; real cause is water in starter solenoid connector.
    ("WO-2507-012", "2025-07-08 06:20", 3.0, "SAP-DG-02", "srinivas", "FTS", "DG-2 failed to start on weekly test run.",
     "Cranked 3 times, no engagement, just a click from the starter. Batteries at 23.1V, a bit low. Replaced both 12V starting batteries. Started on the first crank. Closed.",
     "Weak starting batteries (suspected)", "fixed", ["2 x 12V 180Ah battery"], 3.0),
    ("WO-2507-049", "2025-07-19 06:40", 2.5, "SAP-DG-02", "srinivas", "FTS", "DG-2 fail-to-start again, 11 days after new batteries.",
     "Same symptom. New batteries at 25.4V, so it is not the batteries. Click but no crank. Cleaned the battery terminals. Started on the 4th attempt. B2 yard had 3 inches of standing water after last night's rain. Could not reproduce the fault afterwards.",
     "Unknown - intermittent", "not_fixed", [], 2.5),
    ("WO-2508-003", "2025-08-02 06:15", 2.0, "SAP-DG-02", "ravi", "FTS", "Third fail-to-start on DG-2 in monsoon.",
     "The pattern is rain. The starter solenoid connector sits low on the block, about 20 cm above the yard floor, and it gets splashed. Found green corrosion and moisture inside the solenoid spade connector. Cleaned it, packed it with dielectric grease, fitted a heat-shrink boot and rerouted the harness 30 cm higher. Starts clean every time. Batteries were never the problem; the July battery swap was wasted money (₹38,000). DG-1 has the same harness routing, so do it before next monsoon.",
     "Moisture/corrosion in starter solenoid connector (low harness routing, flooded B2 yard)", "fixed", ["Dielectric grease", "Heat-shrink boot", "Cable ties"], 2.0),
    ("WO-2606-008", "2026-06-05 06:30", 1.5, "SAP-DG-01", "srinivas", None, "Pre-monsoon harness reroute on DG-1 as advised.",
     "Applied the DG-2 fix to DG-1 before the rains: cleaned the solenoid connector (light corrosion already), dielectric grease, boot, harness rerouted up. Fixed pre-emptively.",
     "Preventive: solenoid connector protection", "advisory", ["Dielectric grease", "Heat-shrink boot"], 0.0),

    # ---- Pattern 4: Meridian lift B3 door fault DF-21. Light-curtain replacement fails; real cause is sill debris + belt tension.
    ("WO-2509-020", "2025-09-10 10:15", 3.0, "MER-LFT-B3", "imran", "DF-21", "Lift B3 doors repeatedly reopening; DF-21 door close timeout logged.",
     "DF-21 x37 in the last 24h. Light curtain looked dirty and was intermittently blocked in diagnostics. Replaced the light curtain pair (₹38,500). Doors closed fine during testing. Closed.",
     "Faulty light curtain (suspected)", "fixed", ["Light curtain pair LC-2000"], 3.0),
    ("WO-2509-061", "2025-09-24 12:30", 2.0, "MER-LFT-B3", "imran", "DF-21", "DF-21 back, worst at lunch hours.",
     "Faults cluster 12:00-14:30. The new light curtain is fine. Door jerks at the last 5 cm on floors 3 and 4 only. Could not find the cause. Adjusted the door close torque slightly.",
     "Unknown", "not_fixed", [], 2.0),
    ("WO-2510-005", "2025-10-03 13:00", 2.5, "MER-LFT-B3", "ravi", "DF-21", "Joint visit with Imran on DF-21 repeat.",
     "Watched the car at lunch. The food-court catering carts on L3 drag food debris and plastic wrap into the landing door sill tracks on floors 2 to 4. The door shoe binds in the last few cm and the controller times out (DF-21). Also found the door operator belt 12 mm slack. Vacuumed and cleaned the sill tracks on L2-L4, re-tensioned the belt to spec. Zero DF-21 in the 3 hours after. Asked FM Anitha to put brush strips on the sills and have housekeeping clean them daily. The light curtain replacement last month was not needed.",
     "Sill track debris from catering carts plus slack door operator belt", "fixed", ["Sill brush strip x3"], 2.5),
    ("WO-2603-033", "2026-03-18 12:50", 1.0, "MER-LFT-B2", "imran", "DF-21", "DF-21 on sister car B2 at lunch time.",
     "Same pattern as B3. Checked the L3 sill first: packed with debris. Cleaned it and checked belt tension (OK). Fixed in 1 hour.",
     "Sill track debris (food court floor)", "fixed", [], 1.0),

    # ---- Pattern 5: Helix UPS battery degradation due to UPS room AC
    ("WO-2505-077", "2025-05-28 11:00", 2.0, "HLX-UPS-01", "lakshmi", "BAT-HT", "UPS battery temperature high alarm.",
     "Battery string temperature 38°C. UPS room split AC blowing warm air: gas low. Informed FM. Battery float voltage OK.",
     "UPS room AC failure", "advisory", [], 0.0),
    ("WO-2601-041", "2026-01-22 10:30", 3.0, "HLX-UPS-01", "lakshmi", "BAT-WEAK", "Battery test failed; autonomy 6 min vs 15 min design.",
     "Impedance test: 11 of 40 blocks in string A high. These batteries are only 4.5 years old. Most likely cause is last summer's 38°C room temperature (every 10°C above 25°C roughly halves VRLA life). Replacing string A (₹4.2 lakh quote). Strongly recommend a redundant AC for the UPS room. The single split AC failed again in May.",
     "Premature VRLA degradation from high room temperature", "fixed", ["40 x 12V 100Ah VRLA"], 0.0),

    # ---- Customer & ops lessons
    ("WO-2508-090", "2025-08-27 14:00", 3.5, "LAK-CH-02", "srinivas", "A-212", "Low evaporator refrigerant temperature trip.",
     "Chilled water flow low. Strainer on primary pump 1 clogged. Cleaned strainer, flow restored. Sent Farah photos every 30 minutes this time and an RCA note the same evening. She appreciated it.",
     "Clogged chilled-water strainer causing low flow", "fixed", [], 3.5),
    ("WO-2512-018", "2025-12-04 09:00", 6.0, "MER-DG-01", "arjun", "LOP", "Low oil pressure shutdown during test.",
     "Reached the SEZ at 9:00 but the gate pass took 45 minutes because it wasn't pre-registered. Oil level OK. Oil pressure sender reading erratic. Replaced sender, DG ran 1 hour loaded with normal oil pressure (380 kPa).",
     "Faulty oil pressure sender", "fixed", ["Oil pressure sender OPS-10"], 1.5),
    ("WO-2603-051", "2026-03-27 09:20", 1.0, "ORB-CH-03", "arjun", None, "Brazing job rescheduled.",
     "Came to braze a leaking flare joint on the standby unit. Job refused: it was Friday and there is no hot work on Fridays at Orbit because of tenant audits. Permit also needed before 9 AM. Rescheduled to Monday. Lost half a day.",
     "Site rule: no hot work on Fridays", "advisory", [], 0.0),
    ("WO-2603-058", "2026-03-30 08:30", 2.5, "ORB-CH-03", "arjun", "LEAK", "Refrigerant leak on circuit 2 flare joint.",
     "Permit raised at 8:10, escort arranged with Sudhakar sir for terrace key. Brazed joint, pressure tested with nitrogen at 1,700 kPa for 1h, vacuumed to 500 microns, recharged 6 kg R-134a.",
     "Leaking flare joint", "fixed", ["R-134a 6 kg", "Brazing rods"], 0.0),
    # ---- Temporal supersedence: CH-02 drives replaced; panel-fan advice becomes obsolete; new failure mode appears
    ("WO-2608-041", "2026-08-18 08:30", 9.0, "ORB-CH-02", "ravi", None, "Planned retrofit: replace all four condenser fan VFDs.",
     "Replaced all four condenser fan VFDs on CH-02 with Kryo SD-40 sealed IP55 drives (heatsink outside the enclosure, no panel cooling fan, no filter). The panel-fan and filter checks from WO-2505-012 and WO-2607-015 NO LONGER APPLY to CH-02; CH-01 still has the old drives. Important commissioning note: SD-40 drives ship with 'Quiet Mode' (parameter P-212) ENABLED from the factory. It caps fan speed at 85% whenever ambient is above 35°C, which is exactly when we need 100%. I disabled P-212 on all four drives. If an SD-40 is ever replaced or factory-reset, P-212 must be disabled again or the chiller will run high head pressure on hot afternoons.",
     "Planned retrofit (obsolete drives)", "advisory", ["4 x Kryo SD-40 sealed VFD"], 9.0),
    ("WO-2609-038", "2026-09-15 11:20", 2.0, "ORB-CH-02", "lakshmi", "VFD-COMM", "Fan bank 2 drive lost comms after DG changeover.",
     "Utility outage and DG changeover at Orbit at 10:50. After restoring power, the CH-02 fan bank 2 SD-40 drive showed a comms fault and would not respond. OEM remote support walked me through a factory reset of the bank 2 drive. Drive came back, fan running, comms OK. Chiller back in service at 13:10.",
     "Drive comms fault after power event; bank 2 drive factory-reset", "fixed", [], 2.3),
    ("WO-2607-015", "2026-07-11 16:00", 2.0, "ORB-CH-02", "ravi", "A-140", "A-140 on CH-02 circuit 2.",
     "Checked fan bank 2 VFD first as usual: F-07 x6. Panel filter blocked again (construction next door still going). Replaced filter, stable. Changing this panel filter every 2 months in summer would prevent this. Arjun shadowed.",
     "Fan VFD derating - blocked panel filter", "fixed", ["Panel filter mat"], 1.5),
]


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def build_story() -> list[dict]:
    jobs = []
    for (wo, opened, dur, asset, tech, alarm, symptom, notes, root, outcome, parts, down) in STORY:
        o = _dt(opened)
        jobs.append(
            {
                "wo_id": wo,
                "asset_id": asset,
                "site": ASSET[asset]["site"],
                "opened_at": o.isoformat(),
                "closed_at": (o + timedelta(hours=dur)).isoformat(),
                "technician": tech,
                "alarm_code": alarm,
                "symptom": symptom,
                "notes": notes,
                "root_cause": root,
                "outcome": outcome,
                "parts": parts,
                "downtime_hours": down,
                "kind": "corrective" if outcome in ("fixed", "not_fixed", "false_alarm") else "advisory",
            }
        )
    return jobs


# ----------------------------------------------------------------------------- routine noise
PM_TEMPLATES = {
    "chiller": [
        ("Quarterly PM", "Checked oil level and oil pressure differential, leak test with electronic detector (no leaks), approach temperatures within spec ({a:.1f}°C evap approach), cleaned control panel, tightened power terminals. Compressor amps {amp} A balanced."),
        ("Monthly inspection", "Logged pressures: suction {sp} kPa, discharge {dp} kPa. Superheat {sh} K. Chilled water in/out {ci}/{co}°C. No alarms in history. Unit healthy."),
    ],
    "dg_set": [
        ("Monthly load test", "Ran on load bank at {load}% for 1 hour. Coolant {ct}°C, oil pressure {op} kPa, frequency 50.0 Hz. Battery {bv} V. Fuel {fuel}% in day tank. No abnormalities."),
        ("250-hour service", "Changed engine oil and oil/fuel filters, checked belt tension and coolant level, cleaned air filter. Test run OK."),
    ],
    "lift": [
        ("Monthly lift maintenance", "Lubricated guide rails, checked brake operation, door operation, levelling accuracy (+/-{lev} mm), emergency alarm and intercom tested. Fault log: {nf} minor events."),
    ],
    "ups": [
        ("Quarterly UPS PM", "Checked input/output voltages, ran battery discharge test (autonomy {aut} min), cleaned fans and filters. Battery room {rt}°C."),
    ],
    "ahu": [
        ("Monthly AHU PM", "Replaced pre-filters, checked belt tension (adjusted {belt} mm), cleaned drain pan, greased bearings. Supply air {sa}°C."),
    ],
    "pump": [
        ("Quarterly pump PM", "Checked mechanical seal (no leak), vibration {vib} mm/s, bearing temperature {bt}°C, VFD fault log clear. Motor current {amp} A."),
    ],
}

MINOR_FAULTS = {
    "ahu": [("Belt squeal", "Fan belt glazed and slack. Replaced belt B-58 and aligned pulleys.", "Worn fan belt", ["V-belt B-58"])],
    "pump": [("Seal weeping", "Mechanical seal weeping on pump. Replaced seal kit.", "Worn mechanical seal", ["Seal kit MS-55"])],
    "chiller": [("Sensor fault", "Chilled water leaving temp sensor open circuit. Replaced 10k thermistor.", "Failed temperature sensor", ["10k thermistor"])],
    "lift": [("Car lighting", "Car LED panel flickering. Replaced driver.", "Failed LED driver", ["LED driver 40W"])],
}


def build_routine(start: datetime, end: datetime) -> list[dict]:
    jobs = []
    n = 0
    for a in ASSETS:
        if a["id"] == "HLX-CH-04":
            continue
        t = a["type"]
        templates = PM_TEMPLATES[t]
        cur = start + timedelta(days=random.randint(0, 25))
        step = {"chiller": 75, "dg_set": 60, "lift": 75, "ups": 150, "ahu": 90, "pump": 150}[t]
        while cur < end:
            title, tpl = random.choice(templates)
            text = tpl.format(
                a=random.uniform(1.2, 2.4), amp=random.randint(180, 260), sp=random.randint(290, 340), dp=random.randint(1050, 1350),
                sh=random.randint(5, 9), ci=round(random.uniform(11.5, 13), 1), co=round(random.uniform(6.5, 7.5), 1), load=random.choice([60, 70, 75]),
                ct=random.randint(78, 88), op=random.randint(360, 420), bv=round(random.uniform(25.2, 26.4), 1), fuel=random.randint(55, 95),
                lev=random.randint(2, 5), nf=random.randint(0, 4), aut=random.randint(13, 17), rt=random.randint(24, 29), belt=random.randint(3, 8),
                sa=round(random.uniform(12.5, 15), 1), vib=round(random.uniform(1.2, 3.1), 1), bt=random.randint(45, 62),
            )
            tech = {"chiller": ["srinivas", "ravi", "arjun"], "dg_set": ["srinivas", "arjun"], "lift": ["imran"], "ups": ["lakshmi"], "ahu": ["arjun", "srinivas"], "pump": ["arjun", "srinivas"]}[t]
            opened = cur.replace(hour=random.choice([8, 9, 10, 11, 14]), minute=random.choice([0, 15, 30, 45]))
            n += 1
            jobs.append({
                "wo_id": f"WO-{opened:%y%m}-{500 + n:03d}",
                "asset_id": a["id"], "site": a["site"], "opened_at": opened.isoformat(),
                "closed_at": (opened + timedelta(hours=random.choice([1, 1.5, 2]))).isoformat(),
                "technician": random.choice(tech), "alarm_code": None, "symptom": title, "notes": text,
                "root_cause": "Planned maintenance", "outcome": "pm", "parts": [], "downtime_hours": 0.0, "kind": "pm",
            })
            # occasional minor fault
            if t in MINOR_FAULTS and random.random() < 0.12:
                sym, notes, root, parts = random.choice(MINOR_FAULTS[t])
                fo = opened + timedelta(days=random.randint(5, 20), hours=2)
                if fo < end:
                    n += 1
                    jobs.append({
                        "wo_id": f"WO-{fo:%y%m}-{500 + n:03d}", "asset_id": a["id"], "site": a["site"], "opened_at": fo.isoformat(),
                        "closed_at": (fo + timedelta(hours=1.5)).isoformat(), "technician": random.choice(tech), "alarm_code": None,
                        "symptom": sym, "notes": notes, "root_cause": root, "outcome": "fixed", "parts": parts,
                        "downtime_hours": 1.0, "kind": "corrective",
                    })
            cur += timedelta(days=step + random.randint(-4, 4))
    return jobs


# ----------------------------------------------------------------------------- today's dispatch board
OPEN_TICKETS = [
    {
        "wo_id": "WO-2609-114", "asset_id": "ORB-CH-02", "priority": "P1", "opened_at": "2026-09-28T14:10:00",
        "technician": "arjun", "alarm_code": "A-140",
        "symptom": "CH-02 tripped on A-140 high discharge pressure, circuit 2. Ambient 36°C. Tenant IT floors 9-11 reporting rising temperatures.",
        "reported_by": "BMS auto-ticket + FM Sudhakar Rao",
    },
    {
        "wo_id": "WO-2609-121", "asset_id": "SAP-DG-02", "priority": "P2", "opened_at": "2026-09-28T06:25:00",
        "technician": "arjun", "alarm_code": "FTS",
        "symptom": "DG-2 failed to start during the weekly test run. Starter clicks, no crank. Heavy rain overnight.",
        "reported_by": "FM Mahesh Chary",
    },
    {
        "wo_id": "WO-2609-127", "asset_id": "MER-LFT-B3", "priority": "P2", "opened_at": "2026-09-28T12:40:00",
        "technician": "arjun", "alarm_code": "DF-21",
        "symptom": "Tower B car 3 doors keep reopening, DF-21 door close timeout x22 since noon. Passengers complaining.",
        "reported_by": "Helpdesk - Anitha Joseph",
    },
    {
        "wo_id": "WO-2609-130", "asset_id": "HLX-CH-01", "priority": "P2", "opened_at": "2026-09-28T10:05:00",
        "technician": "arjun", "alarm_code": "A-140",
        "symptom": "A-140 high discharge pressure on circuit 1 at 29°C ambient. Unit restarted once and tripped again.",
        "reported_by": "BMS auto-ticket",
    },
    {
        "wo_id": "WO-2609-133", "asset_id": "HLX-CH-04", "priority": "P3", "opened_at": "2026-09-28T15:30:00",
        "technician": "arjun", "alarm_code": "A-140",
        "symptom": "Newly commissioned CH-04 logged two A-140 warnings on circuit 2 this afternoon (no trip yet). Fan bank 2 sounds slower than the others.",
        "reported_by": "FM Pradeep Menon",
    },
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    story = build_story()
    routine = build_routine(datetime(2025, 3, 1), datetime(2026, 9, 25))
    history = sorted(story + routine, key=lambda j: j["opened_at"])
    for path, obj in [
        ("sites.json", SITES), ("technicians.json", TECHS), ("assets.json", ASSETS),
        ("history.json", history), ("open_tickets.json", OPEN_TICKETS),
    ]:
        (OUT / path).write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    print(f"sites={len(SITES)} techs={len(TECHS)} assets={len(ASSETS)} history={len(history)} "
          f"(story={len(story)}, routine={len(routine)}) open={len(OPEN_TICKETS)}")


if __name__ == "__main__":
    main()
