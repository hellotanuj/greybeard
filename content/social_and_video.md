# Content kit

Rule for everything below: do not frame any of this as an event or competition project, including in hashtags.

---

## 1. Article title options (Prompt 1)

Chosen: **My agent told a technician to ignore its own best advice, and it was right**

1. My agent told a technician to ignore its own best advice
2. I built an agent that remembers which fixes didn't work
3. Why my maintenance agent ranks failed fixes above successful ones
4. How Hindsight caught a fix that stopped being true
5. Vector search kept recommending a part that no longer existed
6. What I learned storing 18 months of repair logs in Hindsight
7. How I stopped a junior technician repeating a ₹38,000 mistake
8. Teaching an agent that old advice can expire
9. I gave my agent a senior technician's memory before he retired
10. The chiller fix that RAG got wrong and Hindsight didn't
11. How I built a briefing agent on one Hindsight reflect call
12. Why I store "didn't work" as a first-class memory
13. My agent learned a defect from three chillers at two sites
14. How I made "the agent learns over time" visible with Hindsight
15. What a 22-year technician taught me about agent memory
16. I replaced top-k retrieval with Hindsight and the briefings changed
17. How I built a manual nobody wrote, using Hindsight mental models
18. Debugging an agent that trusted last year's fix
19. Why timestamps mattered more than embeddings in my agent
20. I built an agent that briefs technicians before they touch anything

---

## 2. LinkedIn post (Prompt 3) — under 800 characters

> Replace `<REPO_URL>` and put the article URL in the first comment.

```
Most agent memory demos remember your name. Mine remembers which fixes didn't work.

I built Greybeard, a briefing agent for technicians who maintain chillers, generators and lifts.

What changed once it had real memory (Hindsight):

Before: "Clean the coils, check refrigerant."
After: "Drive was reset on 15 Sep, so Quiet Mode is back on. Check P-212 first (10 min). Skip the coil wash, it failed twice."

3 things I'd copy tomorrow:
1. Store failed fixes as first-class memories
2. Timestamp by when it happened, not when you ingested it
3. Put invariants (cite sources, prefer recent state) in directives, not prompts

It even flags last year's fix as obsolete after a retrofit.

Code: <REPO_URL>

#AIAgents #AgentMemory #Hindsight #LLM #AI
```

First comment: `Article: <ARTICLE_URL>`
Second comment: `Here's a link to Hindsight if you want to check it out: https://github.com/vectorize-io/hindsight`

---

## 3. Reddit (link post)

- Subreddits: r/aiagents, r/LLMDevs, r/aimemory, r/SideProject
- Title: same as article title
- Link: article URL

---

## 4. Video script (~3 min)

**Setup:** app open at localhost:8000, fonts bumped, notifications off. Seed already complete.

**0:00 – 0:30 · Intro (on camera, then screen)**
"Hi, I'm <NAME>. This is Greybeard, a briefing agent for field technicians who maintain chillers, generators and lifts. In facility services, the answer to most breakdowns is already in someone's head, usually the most senior technician's. This one, Ravi, retires in December. Greybeard keeps what he knows, using Hindsight as its memory."
*Screen: dispatch board, hover the five tickets.*

**0:30 – 1:00 · The problem**
"Arjun has eight months in the field. His first job: a P1 chiller trip at Orbit Towers, high discharge pressure."
*Click ORB-CH-02 → Raw asset log tab.* "This is the history for this one unit. Nobody reads this on a phone in a 41-degree plant room."
*Click Pre-job briefing → Brief Arjun.* "On the left is a stateless model with no memory. Clean the coils, check refrigerant. It's reasonable, and it would cost him an afternoon."

**1:00 – 2:30 · Demo: memory in action**
*Right column fills in.* "Greybeard is one Hindsight reflect call with a JSON schema. It says the fan drive on bank 2 was factory-reset two weeks ago, which silently turns Quiet Mode back on. Check parameter P-212 first, ten minutes."
*Point at Superseded.* "This is where plain RAG fails. Last year's fix was the drive's panel fan, and that's still the most similar document. But the drives were replaced in August, so Greybeard strikes it out."
*Point at Don't repeat.* "It also warns him off the coil wash that failed twice."
*Click a WO chip → history row highlights.* "Every claim cites the work order."
*Flip Memory as of: Day 1 → Jun 2025 → Dec 2025 → Today.* "These are real Hindsight banks seeded to different dates. Watch the advice get sharper as memory grows."
*Close out & teach → Fill demo close-out → Submit.* "Arjun closes the job. It's retained immediately, and so is his feedback on whether the briefing was right."
*Open HLX-CH-04 → Brief.* "This chiller was installed last month and has zero history. Greybeard still says check P-212, because the fleet learned it."
*Fleet Knowledge tab.* "These pages are Hindsight mental models. Nobody wrote them. They rewrite themselves after every consolidation."

**2:30 – 3:00 · Takeaway**
"What surprised me: the most valuable memories were the failures. 'Tried this, didn't work' is what saves the afternoon. And it only works because Hindsight tracks time, so it knows when good advice has expired. Code's on GitHub."

**YouTube title options**
1. My AI agent told a technician to ignore last year's fix
2. I gave an AI agent 18 months of repair logs. Here's what it learned
3. RAG vs real agent memory: a chiller breakdown
4. The agent that remembers which fixes DIDN'T work
5. Building a senior technician's memory with Hindsight

---

## 5. Thumbnail prompt (Nano Banana, 16:9) — attach a team photo

```
Generate a viral thumbnail for this YouTube video. Make the thumbnail attention grabbing and something that people
scrolling would want to click on if they see it. The aspect ratio needs to be 16:9.

Scene: the person in the attached photo on the right, looking surprised, wearing a hi-vis vest, standing in front of a
rooftop industrial chiller at golden hour. On the left, a phone screen showing a dark app card with a red crossed-out line
"REPLACE PANEL FAN" and a glowing amber line "CHECK P-212 FIRST - 10 MIN". Big bold text at top: "IT REMEMBERED WHAT FAILED".
Dark graphite and amber colour palette, high contrast, crisp.

Here is the video script:
[paste section 4]
```
