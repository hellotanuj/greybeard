# My agent told a technician to ignore its own best advice, and it was right

The most useful thing my maintenance agent does is tell a junior technician *not* to follow the fix that worked last year.

Last summer, a 500-ton chiller on the terrace of an office tower in Hyderabad's Financial District kept tripping on high discharge pressure every afternoon. Two coil washes didn't fix it. Then Ravi, a technician with 22 years in the trade, walked up, ignored the coils, opened the fan drive's fault log and found a seized cooling fan inside the VFD panel. The drive was throttling one condenser fan bank to 60% exactly when the head pressure peaked. It was a ₹1,800 part.

That fix went into the logbook. This August, the same chiller got new sealed fan drives with no panel fan at all. So when it tripped again last week, the most "relevant" record in the history, the one any similarity search would put first, was now wrong.

I built [Greybeard](https://github.com/) so that knowledge like Ravi's doesn't retire with him, and so the agent knows when that knowledge has gone stale. This post covers how it works, why I built it on [Hindsight agent memory](https://github.com/vectorize-io/hindsight) instead of a vector store, and what I got wrong along the way.

## The problem: first-time fix is a memory problem

Facility-services companies maintain chillers, diesel generators, lifts and UPS systems for dozens of buildings. Their CMMS holds thousands of work orders. In theory the answer to most breakdowns is already in there. In practice:

- Nobody scrolls 40 entries on a phone in a 41°C plant room.
- Logs record what was done, not "this didn't work, don't bother".
- Patterns cross assets. A defect in one serial batch shows up on three units at three different sites.
- The person who connects those dots is usually the most senior technician, and they eventually leave.

The business metric is first-time-fix rate. Every repeat visit is a truck roll, a technician's half day and a tenant complaint. When I looked at why repeat visits happen, most of them came down to someone not knowing what someone else already learned.

## What Greybeard does

A technician opens a job, for example *ORB-CH-02 tripped on A-140, circuit 2, 36°C ambient*, and gets a briefing:

- **Check first**: ordered steps with time estimates, fastest first
- **Don't repeat**: fixes tried on this unit or model that didn't work
- **Superseded knowledge**: advice that used to be right until the equipment changed
- **Likely causes**: ranked, with evidence
- Parts to carry, site rules, and who to call if stuck

Every claim links to the work orders it came from. When the job is done, the technician logs what actually fixed it and whether the briefing was right. Both go back into memory immediately.

The UI shows the same question answered twice, side by side: once by a stateless LLM, once by Greybeard. The only thing that differs is memory.

## Why I didn't use a vector store

My first instinct was the standard RAG pipeline: chunk the work orders, embed them, retrieve the top-k, stuff them into a prompt. It fails on exactly the cases that matter.

1. **Recency conflicts.** The 2025 panel-fan fix is semantically closer to "A-140 on CH-02" than the August retrofit note is. Top-k happily returns the obsolete fix.
2. **Multi-hop.** Last week's trip was caused by the fan drive being factory-reset during a generator changeover, which silently re-enabled a "Quiet Mode" parameter that caps fan speed above 35°C. The ticket mentions none of that. You have to join three separate facts: the retrofit, the parameter default, and the reset.
3. **Failure as signal.** "Coil wash, problem came back" and "coil wash, fixed" embed almost identically.

[Hindsight](https://hindsight.vectorize.io/) takes a different approach. `retain` runs LLM extraction over everything you give it, producing facts, entities, relationships and timestamps. `recall` runs semantic, keyword, entity-graph and temporal retrieval in parallel and fuses them. In the background, related facts get consolidated into *observations*, deduplicated beliefs with evidence attached, which are refined rather than overwritten when new evidence arrives. That last part is the behaviour I needed for "this used to be true".

## Shaping the memory

Each work order is retained as its own document, stamped with the time the job actually closed and tagged along the axes a technician thinks in:

```python
def tags_for(job: dict, asset: dict) -> list[str]:
    tags = [
        f"asset:{job['asset_id']}",
        f"site:{asset.get('site', job.get('site', 'unknown'))}",
        f"type:{asset.get('type', 'unknown')}",
        f"model:{slug(asset.get('model', 'unknown'))}",
        f"outcome:{job.get('outcome', 'unknown')}",
    ]
    if job.get("technician"):
        tags.append(f"tech:{job['technician']}")
    return tags
```

`outcome:not_fixed` is a first-class tag. Failed fixes are the most valuable memories in the whole system.

The bank itself gets a retain mission that tells extraction what matters in this domain:

```python
RETAIN_MISSION = (
    "Extract: equipment faults and alarm codes; measured readings; the root cause; "
    "the fix that worked; fixes that were tried and did NOT work (and why); parts used; "
    "site access rules and safety constraints; customer preferences; which technician did what. "
    "Always preserve work order IDs, asset IDs, equipment models and serial-number batches verbatim."
)
```

Preserving serial batches verbatim is what makes this link possible: "HLX-CH-01 is a 2019-batch unit" → "the 2019 batch used the older pressure transducer revision" → "if A-140 shows up at low ambient, put a manifold gauge on it before washing anything". That hop crosses three work orders on three different chillers at two sites.

## The briefing is one `reflect` call

I don't hand-roll a retrieval-then-prompt loop. The briefing is a single Hindsight `reflect` call with a JSON schema:

```python
resp = await self.client.areflect(
    bank_id, query, context=context, budget="mid",
    response_schema=BRIEFING_SCHEMA,   # check_first, avoid, superseded, likely_causes, ...
    include_facts=True,                # return the exact memories used -> UI citations
)
```

`reflect` searches mental models first, then observations, then raw facts. With `include_facts=True` it returns the memories it actually used, which is what powers the citation chips in the UI. If a sceptical technician asks "where did that come from?", the answer is one click away.

Behaviour that has to be deterministic goes into **directives**, not prompt text:

```python
DIRECTIVES = [
    ("cite-evidence", "Every claim based on past jobs must cite the supporting work order IDs.", 10),
    ("flag-failed-fixes", "If a fix was tried before on this asset or model and did not solve the problem, "
                          "explicitly warn the technician not to repeat it and say what worked instead.", 9),
    ("prefer-recent", "When older and newer memories about the same asset conflict (replaced, retrofitted, reset), "
                      "trust the most recent state and explicitly list the older advice as superseded.", 9),
    ("safety-first", "Always remind the technician to apply lockout/tagout before working on electrical "
                     "or rotating equipment.", 8),
]
```

The bank's disposition is set to skepticism 4, literalism 3, empathy 2. I wanted a senior engineer who says "memory has nothing on this, here's the generic OEM procedure, labelled as generic" rather than one who confidently invents history.

## Before and after

Same ticket, same model underneath:

**Without memory:**
> Check condenser coils for fouling and clean if required. Verify refrigerant charge. Check condenser fan operation. Inspect high-pressure switch.

**Greybeard:**
> **High confidence.** The fan bank 2 drive was factory-reset on WO-2609-038, so Quiet Mode (P-212) is likely back on and capping the fan at 85% above 35°C. Check P-212 first (~10 min).
> **Superseded:** ~~Replace VFD panel fan~~. CH-02's drives were replaced with sealed SD-40 units in Aug 2026 (WO-2608-041). There is no panel fan any more.
> **Don't repeat:** Coil wash. It was tried twice in April 2025 and the trip came back (WO-2504-031, WO-2504-058).
> **Site:** Raise the permit before 9 AM; terrace key is with FM Sudhakar Rao; no hot work on Fridays.

The generic answer isn't wrong. It's the answer you'd give on day one. The difference is that four hours of coil washing becomes a ten-minute parameter check.

To show that it's memory doing the work, not prompt engineering, the UI has a **"memory as of"** switch. Day 1, June 2025, December 2025 and today are separate Hindsight banks with identical configuration, each seeded only with history up to that date. Flip through them and the briefing goes from generic, to "check the VFD panel fan", to "the panel fan is gone, check P-212".

## The manual nobody wrote

The feature that surprised me most was **mental models**. I defined four questions once: recurring failure patterns by model, fixes that didn't work, site access and customer playbook, and who knows what. Hindsight writes the answers and rewrites them after each consolidation:

```python
await self.client.acreate_mental_model(
    bank_id, id="failed-fixes", name="Fixes that didn't work",
    source_query="Which fixes were tried and failed to solve the problem? For each: asset, what was tried, "
                 "the cost/time wasted, what the real cause turned out to be, and work order IDs.",
    trigger={"refresh_after_consolidation": True, "mode": "delta"},
)
```

Reading one is a database read, with no LLM call on the request path. In delta mode, unchanged sections stay byte-for-byte identical across rewrites, so the page reads like a document that grows, not one that gets paraphrased every night. Facility managers ask for exactly this ("write down what Ravi knows") and it never gets done by hand.

## What I got wrong

- **I started by stuffing everything into one blob per asset.** Extraction was worse and I lost per-job timestamps, which broke the temporal story. One document per work order, with the real close time as the event timestamp, fixed both.
- **My first dataset had no failures in it.** Every job ended "fixed". The agent had nothing to warn about. Realistic data is mostly routine PMs with a few painful stories buried in it, and the stories need the dead ends kept in.
- **I tried to make the stateless baseline look bad.** Pointless. The honest comparison is the same configuration with an empty bank. The generic answer is reasonable, and that's what makes the memory-backed one convincing.
- **Consolidation is asynchronous.** Right after seeding, observations and mental models lag for a few minutes. I now poll bank stats until pending consolidation hits zero before demoing.

## Takeaways

1. **Store failures as first-class memories.** "Tried X, didn't work" is worth more than "did Y, fixed".
2. **Use the real event time as the timestamp, not ingestion time.** Temporal reasoning only works if the memory knows *when* things happened.
3. **Tag along the axes your users reason in.** Asset → model → site gave me "this unit" and "the whole fleet" from one bank.
4. **Put invariants in directives.** Citation, safety reminders and recency preference shouldn't depend on prompt luck.
5. **Show the learning curve, not just before/after.** Snapshot banks at different dates make "the agent improves over time" something you can see.

If you're building agents for work where experience compounds (maintenance, support, operations, sales), the retrieval problem is really a memory problem. [Agent memory](https://vectorize.io/what-is-agent-memory) that consolidates, tracks time and remembers what didn't work is a different primitive from a vector index. Hindsight is [open source](https://github.com/vectorize-io/hindsight) and the [docs](https://hindsight.vectorize.io/) are good. Greybeard's code is on GitHub.
