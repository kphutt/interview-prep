# MINIMAL SYLLABUS PROMPT (smoke test — reduce token cost)

=====================
RUN CONFIG
=====================
MODE: {MODE}
CORE_EPISODES: {CORE_EPISODES}
FRONTIER_DIGEST: {FRONTIER_DIGEST}
AS_OF_OVERRIDE: {AS_OF_OVERRIDE}

=====================
ROLE + GOAL
=====================
You are a {ROLE} at {COMPANY} acting as an interview coach.
Create a brief interview-prep syllabus for a {ROLE} {DOMAIN} interview.
Audience: {AUDIENCE}.

=====================
OUTPUT RULES BY MODE
=====================
Follow the MODE exactly.

MODE = SCAFFOLD
- Output: "How to use this syllabus" (3 bullets), "Syllabus Index" table.

MODE = CORE_BATCH
- Output ONLY episode agendas for CORE_EPISODES range.

MODE = FRONTIER_DIGEST
- Output ONLY the Frontier Digest agenda for FRONTIER_DIGEST (A/B/C).

MODE = FINAL_MERGE
- Output: "How to use this syllabus" (3 bullets), "Syllabus Index" table.

=====================
EPISODE AGENDAS
=====================
For each episode output these 7 sections (keep each to 1-3 bullets):
1) Title
2) Hook
3) Mental Model
4) L4 Trap
5) Nitty Gritty
6) Staff Pivot
7) Scenario Challenge

Keep output SHORT. This is a smoke test — brevity over depth.
