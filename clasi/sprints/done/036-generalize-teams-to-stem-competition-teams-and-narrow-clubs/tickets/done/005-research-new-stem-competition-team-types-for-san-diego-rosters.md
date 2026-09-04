---
id: '005'
title: Research new STEM competition-team types for San Diego rosters
status: done
use-cases:
- SUC-071
depends-on:
- '004'
github-issue: ''
issue: 47-generalize-teams-and-narrow-clubs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Research new STEM competition-team types for San Diego rosters

## Description

Issue 47 asks for a bounded brainstorm-and-hunt for other San Diego
STEM competition-team types, beyond the robotics leagues and the two
ticket 002 just migrated. Starting list (not exhaustive): DOE Science
Bowl, National/Garibaldi Ocean Sciences Bowl, MATHCOUNTS, American
Rocketry Challenge (TARC), SeaPerch, Botball, Envirothon, Future City,
TSA chapters, SkillsUSA chapters, eCyberMission, Zero Robotics, Junior
Solar Sprint, Solar Cup, Math Circle/AMC-AIME school teams, picoCTF,
Mayor's Cyber Cup.

This is genuinely open-ended research, not implementation — this
ticket produces **findings**, no code or data changes. Sprint 029
already registered several of these as *events* in `registry/
sources/*.toml` (`doe-science-bowl-sd.toml`, `garibaldi-bowl.toml`,
`mathcounts-sd-chapter.toml`, `botball-greater-sd.toml`,
`seaperch-sd-regional.toml`, `sd-math-circle.toml`, `cyberpatriot-sd.toml`
already covered by ticket 002) — those pages are event/competition-date
announcements, not team rosters, so they are the *first place to
check* for a roster link, not a substitute for finding one. Apply the
standard held since sprint 027: live-verify, and record "no public
roster exists" as a finding, not a failure — the same discipline
sprint 029's own registry comments already model (several of those
sources are `enabled = false` with a documented, live-verified reason).

## Acceptance Criteria

- [x] All 16 starting-list types (plus any additional type discovered
      along the way, e.g. by following a link from one of the checked
      sources) have a recorded disposition: **roster found and
      verified** (link + what it shows + San Diego-specific team
      count), **no public roster exists** (what was checked and how),
      or **roster exists but not usable** (e.g. paywalled, no
      San-Diego-specific breakout, stale/superseded, requires an
      account) — matching the granularity sprint 029's own registry
      comments use for a disabled source.
- [x] For each of the 7 types sprint 029 already registered as an
      *event* (`doe-science-bowl-sd`, `garibaldi-bowl`,
      `mathcounts-sd-chapter`, `botball-greater-sd`,
      `seaperch-sd-regional`, `sd-math-circle`, plus MATHCOUNTS/
      Envirothon/TSA/SkillsUSA if a matching entry exists), the
      existing registry TOML is checked first for any roster-page
      reference before an independent web search begins.
- [x] Every "roster found" claim is live-verified by an actual fetch
      (WebFetch or a direct `curl`/browser check), not asserted from a
      search-result summary alone — per sprint 029's own corrected
      precedent (ticket 001/002's "first pass never exercised the real
      fetcher" lesson).
- [x] Findings are written into `teams/DESIGN.md`'s Open Questions or a
      dedicated "Sprint 036 research findings" section — not left only
      in this ticket's own file, so a future sprint planner finds them
      without having to re-open sprint 036's tickets.
- [x] No roster is populated by this ticket — that is ticket 006's job,
      gated on this ticket's findings.
- [x] If zero types clear the "real, live, verifiable, San
      Diego-specific roster" bar, that is an acceptable, fully
      documented outcome (matching sprints 027-032's own precedent) —
      this ticket's acceptance criteria are about the *quality and
      completeness of the research*, not about finding a minimum number
      of populatable types.

## Notes — Sprint 036 ticket 005 research findings (2026-09-03)

Every fetch below was a real, live request (`curl` from an unsandboxed
Bash shell, per this environment's own precedent that the WebFetch
tool's request path occasionally 403s where a bare `curl` does not —
see `cipherhacks.toml`'s corrected finding) — not a search-summary
inference. All 7 of sprint 029's own event registrations relevant here
(`doe-science-bowl-sd`, `garibaldi-bowl`, `mathcounts-sd-chapter`,
`botball-greater-sd`, `seaperch-sd-regional`, `sd-math-circle`;
`cyberpatriot-sd` already migrated by ticket 002) were read and their
registered page re-fetched *before* any independent web search began.
No Envirothon/TSA/SkillsUSA registry entry exists to check first.

### Summary table (ordered best-candidate-first)

| # | Type | SD participation confirmed? | Public roster? | Evidence | Disposition | Build/skip |
|---|------|------------------------------|-----------------|----------|--------------|------------|
| 1 | **MATHCOUNTS San Diego Chapter** | Yes | **Yes — 13 schools, named** | cspeef.org 2026 official-results PDF | Roster found and verified | **BUILD** |
| 2 | **American Rocketry Challenge (TARC)** | Yes (1 team) | Yes, thin (1 of likely dozens of local entrants) | rocketrychallenge.org 2026 National Finalists page | Roster found and verified (thin) | **BUILD, marginal** |
| 3 | SkillsUSA chapters | Yes (2 schools) | Partial — award-tier subset only, not a census | skillsusaca.org Chapter of Excellence 2026 | Roster exists but not usable | Skip |
| 4 | Mayor's Cyber Cup / SoCal Cyber Cup | Yes | No — explicitly sponsor-gated | ndia-sd.org event page | Roster exists but not usable | Skip |
| 5 | Zero Robotics | Unconfirmed (1 informal mention) | No — login-gated | zerorobotics.mit.edu | Roster exists but not usable | Skip |
| 6 | DOE Science Bowl (San Diego HS Regional) | Unconfirmed | No — registration portal only | science.osti.gov | No public roster exists | Skip |
| 7 | Garibaldi Bowl (NOSB, San Diego) | Winner only (Canyon Crest Academy) | No | nosb.org; home.sandiego.edu (404) | No public roster exists | Skip |
| 8 | SeaPerch San Diego Regional | Yes (event runs) | No | classroomofthefuture.org | No public roster exists | Skip |
| 9 | Botball Greater San Diego | Unconfirmed | No — page 404 | kipr.org | No public roster exists | Skip |
| 10 | Envirothon | Vague ("LA and SD area schools") | No | rcdsandiego.org, rcrcd.org, envirothon.org | No public roster exists | Skip |
| 11 | Future City | Folds into non-SD "California (Southern)" region hosted at USC/LA | No | futurecity.org/future-city-regions | No public roster exists (not SD-specific) | Skip |
| 12 | TSA chapters | Unconfirmed | No — no live CA chapter directory found | tsaweb.org | No public roster exists | Skip |
| 13 | eCyberMission | One informal 2025 mention | No; also a poor "standing group" fit (ad hoc 2-4 student project team) | secondary coverage only | No public roster exists | Skip |
| 14 | Junior Solar Sprint | Historical only; current local status unknown | No | secondary coverage only, pre-2020 | No public roster exists | Skip |
| 15 | Solar Cup | Not confirmed SD-specific (MWD LA-basin program) | No | mwdh2o.com | No public roster exists (not SD-specific) | Skip |
| 16 | Math Circle / AMC-AIME (SD Math Circle) | SDMC fields one composite all-star team, not per-school teams | No — page stale since 2020 | sdmathcircle.org/events/arml | No public roster exists | Skip |
| 17 | picoCTF | Open, self-forming teams; no institutional/school roster | No; also a poor "standing group" fit | picoctf.org | No public roster exists | Skip |
| — | MATE ROV Competition *(discovered)* | No confirmed San Diego regional | No | materovcompetition.org | No public roster exists / no confirmed SD regional | Skip |
| — | Congressional App Challenge *(discovered; already an sprint-029 event)* | Yes (registered, enabled event) | Not researched to roster depth this ticket (participating-districts page names districts, not teams) | congressionalappchallenge.us | Not fully researched — flag for a future ticket | Defer |

### Recommendation for ticket 006

**Populate MATHCOUNTS San Diego Chapter as the primary new type.** It is
the clear best candidate found this ticket: a complete, dated, named,
San-Diego-specific roster of **13 participating schools** (Black
Mountain Middle, Carmel Valley Middle, Design39Campus, Francis Parker
Middle, Meadowbrook Middle, Mesa Verde Middle, Muirlands Middle, Oak
Valley Middle, Pacific Trails Middle, San Diego French American School,
Sycamore Ridge School, The Bishop's School, Thurgood Marshall Middle),
each fielding a named 4-student team with a named head coach, published
at a stable URL linked directly from the sprint-029 event registration
already on file (`mathcounts-sd-chapter.toml`). It mirrors the
Science Olympiad/CyberPatriot precedent exactly: a school-affiliated,
per-school team roster, not an individual contest.

**Second candidate, offered with an explicit caveat: American Rocketry
Challenge (TARC), thin.** Exactly one San Diego-area team — Del Norte
High School — appears on rocketrychallenge.org's official 2026 National
Finalists page (the top 100 of 1,107 national entrants). This is a
real, live, dated, officially-published result, matching this
project's evidentiary bar — but the source only surfaces the ~9% of
entrants that reach the national cutoff, so it almost certainly misses
most actual San Diego TARC entrants; a `teams.json` league built from it
would ship with exactly 1 team, not a true regional census. Ticket 006
should decide, at execution time, whether a 1-team league is worth
adding (CyberPatriot shipped with 3, so precedent for a small league
exists) or whether to stop at MATHCOUNTS alone and record TARC as a
recorded-but-deferred finding. This ticket does not resolve that
judgment call — it is deliberately left to ticket 006, per this
ticket's own scope boundary against populating anything.

No other candidate — including SkillsUSA's real-but-partial
Chapter-of-Excellence list — cleared the bar; see the Disposition
column above and the per-type detail below for why each fell short.

### Per-type detail

**1. DOE Science Bowl (San Diego High School Regional).** Registered
as event, enabled (`doe-science-bowl-sd.toml`). Checked the registry
TOML first (per its own header) — no roster-page reference recorded
there. Re-fetched `https://science.osti.gov/wdts/nsb/Regional-
Competitions/High-School-Regionals/California/CA_San-Diego-High-
School-Regional-Science-Bowl` directly (`curl`, HTTP 200, 221KB): the
page is a coach-registration portal ("Coach Registration — Register
your team here", a multi-step PREREGISTRATION/Team-1-registration
workflow) with zero participating-school names visible to a public,
unauthenticated fetch — team rosters are built inside the login-gated
registration system. Checked `science.osti.gov`'s national "Competition
Results"/regional-winners press pages and `sandia.gov`'s CA-regional
overview via web search: both publish only national/overall winners
(e.g., "Students from California and Massachusetts win..."), never a
San Diego regional participant list. **No public roster exists.**

**2. Garibaldi Bowl (National Ocean Sciences Bowl, San Diego).**
Registered as event, disabled (dead page, HTTP 404 confirmed on two
prior independent checks per the registry TOML's own header). Checked
the TOML first — its header already documents the 404 and that no
other dedicated page could be found. This ticket's own search
corroborates: `nosb.org/2026-regional-bowl-winning-teams/` names only
the *winning* team per region (Canyon Crest Academy is independently
confirmed, via `sandiego.edu` and `sea-technology.com` press coverage,
as the San Diego/Garibaldi Bowl's own regional winner) — a single-team
announcement, not a roster of the schools that competed. **No public
roster exists** (a winner is known; a roster is not).

**3. MATHCOUNTS San Diego Chapter.** Registered as event, disabled
(`mathcounts-sd-chapter.toml`'s header records a 2026-09-02 HTTP 403
from this project's own `PoliteFetcher` against `cspeef.org/
competitions/san-diego/`). Checked the TOML first, then re-fetched that
exact URL directly via `curl` from an unsandboxed shell (not
WebFetch): it now returns HTTP 200 (96KB) — the WAF block recorded in
the TOML does not reproduce for a bare `curl` request, the same shape
of false-positive `cipherhacks.toml` already documents (WebFetch- or
PoliteFetcher-specific 403 that a real `curl` does not hit). That page
directly links
`https://cspeef.org/wp-content/uploads/2026/03/San-Diego-Chapter-2026-
Competition-Official-Results.pdf` ("San Diego - MATHCOUNTS of
California"). Fetched that PDF (`curl`, HTTP 200, 580KB, 5 pages) and
read it in full: **"2026 San Diego Chapter MATHCOUNTS Competition —
February 28, 2026 — Official Results."** It names all 13 participating
schools (Black Mountain Middle, Carmel Valley Middle, Design39Campus,
Francis Parker Middle, Meadowbrook Middle, Mesa Verde Middle, Muirlands
Middle, Oak Valley Middle, Pacific Trails Middle, San Diego French
American School, Sycamore Ridge School, The Bishop's School, Thurgood
Marshall Middle), each school's 4-student competing team by name, its
head coach, plus 5 named non-school individual competitors, team ranks,
and state-competition advancement. **Roster found and verified** — the
strongest candidate this ticket found. (Note: this does not change the
existing `mathcounts-sd-chapter.toml` event registration's own disabled
status — that source's job is extracting a *dated competition
announcement* via `program_page`/LLM extraction and is a separate
concern from a *curated static roster* built from this results PDF's
contents, the same distinction ticket 001-002 already drew between
Science Olympiad's disabled `sd-science-olympiad.toml` event source and
its populated `team_static_roster` entry.)

**4. American Rocketry Challenge (TARC).** No existing registry entry
(not one of sprint 029's 7). Searched `rocketrychallenge.org`'s
official results; fetched (`curl`, HTTP 200, 82KB)
`https://www.rocketrychallenge.org/result/2026-finalists/`, the
official "2026 National Finalists" page (top 100 of 1,107 teams
nationally that qualified for the May 2026 National Finals). Read the
full team/city/state table: exactly one San Diego-area entry — **Del
Norte High School, San Diego, California**. Checked every other San
Diego County city name (Chula Vista, Poway, Escondido, Carlsbad,
Oceanside, El Cajon, La Mesa, Vista, San Marcos, Encinitas, Coronado,
Santee, National City, Imperial Beach) against the same fetched text —
none appear (only "La Jolla" matched, as a substring of "La Jolla"
inside an unrelated string, not a second SD team). Searched for a
broader "all 1,107 teams" list (2025 had one, `rocketcontest.org/news/
2025-team-list/`); no 2026 equivalent could be found — likely not yet
published this cycle. **Roster found and verified, but thin**: real,
live, dated, official, and San-Diego-specific, but structurally
captures only the ~9% of entrants reaching the national cutoff.

**5. SeaPerch (San Diego Regional).** Registered as event, enabled
(`seaperch-sd-regional.toml`). Checked the TOML first — no roster-page
reference recorded (its header discusses date-extraction only).
Re-fetched `https://classroomofthefuture.org/seaperch-san-diego-
regional-competition/` directly (`curl`, HTTP 200, 95KB) and read the
full page body: registration/rules/logistics content only ("assigned
team #", TDR-submission instructions, a Google-Form signup link) —
zero participating team or school names, before or after the fact.
Checked `seaperch.org`'s own results page (`2026-international-
seaperch-challenge-final-standings`): it covers the *international*
final only, where the sole confirmed San Diego-area qualifier,
"Soakyo-Drift" from the US Naval Sea Cadet Corps (San Diego), appears —
a Sea Cadets-sponsored team, and Sea Cadets was already dropped from
this project's scope entirely by ticket 003. **No public roster
exists** for a San Diego-specific team census.

**6. Botball (Greater San Diego).** Registered as event, disabled
(`botball-greater-sd.toml`'s header records a prior "no calendar date
reaches the model" finding, reproduced 4/4). Checked the TOML first —
no roster-page reference recorded. The search-indexed URL for a
region-team-list page (`kipr.org/botball/schedule-regions/regions-
teams/greater-san-diego`) 404s on a direct `curl -L` fetch (confirmed
live) — KIPR's site structure appears to have moved or removed that
page since the search index was built. **No public roster exists** at
the URL found; not re-attempted at other guessed URLs, per this
ticket's bounded scope (flagged for a future ticket to re-probe KIPR's
current sitemap if this type is revisited).

**7. Envirothon.** No existing registry entry. Searched for a San
Diego-specific program; found `rcdsandiego.org` ("Resource Conservation
District of Greater San Diego County," already registered in this
project's registry as `rcdsandiego.toml`, unrelated adapter) hosts a
"Supporting High School Conservationists" page, and secondary sources
state generically that "high schools from the Los Angeles and San
Diego area participate" in the statewide California Envirothon (a
recent cycle was held in Bakersfield — not a San-Diego-local event).
No named list of which San Diego schools/teams enter could be found on
`rcdsandiego.org`, `rcrcd.org` (Riverside-Corona's own Envirothon page,
a different RCD entirely), or `envirothon.org`. **No public roster
exists.**

**8. Future City.** No existing registry entry. Fetched (`curl`, HTTP
200) `futurecity.org`'s own "Future City Regions" directory
(`/future-city-regions/`) live: confirmed there is **no separate San
Diego region** — San Diego falls under "California (Southern)," whose
regional event is hosted at USC Viterbi School of Engineering in Los
Angeles. `stemforward.org`'s "Future City Competition" page (a search
hit) turned out to be the *Wisconsin* region's own site, an unrelated
organization by coincidental page title — not a San Diego lead.
**No public roster exists (not a San Diego-specific competition)** —
the same "regional folds into a non-SD-specific event" shape Solar Cup
and Future City both hit.

**9. TSA (Technology Student Association) chapters.** No existing
registry entry. Searched for a California TSA chapter directory or
state-conference results archive; found only `tsaweb.org` (national)
and California TSA's social-media presence (Facebook/X) — no live
`californiatsa.org` chapter-list or competition-results page could be
located via search. **No public roster exists** (could not locate a
live California TSA chapter directory or results archive naming San
Diego-area chapters).

**10. SkillsUSA chapters.** No existing registry entry. Fetched
(`curl`, HTTP 200, 1.18MB) `https://www.skillsusaca.org/chapter-of-
excellence` directly: a real, dated (2026) "SkillsUSA California 2026
Chapters of Distinction" list naming **two San Diego County schools** —
Granite Hills High School (El Cajon, Grossmont Union High School
District) at the top "Models of Excellence" tier, and Oceanside High
School at "Silver Medalist" tier — among ~50 statewide chapters listed.
This is real, live, dated, and named — but it is an internal
chapter-quality certification program ("Level One Quality Chapter
Required to Compete"), not a competition-results roster or a chapter
directory: it names only the subset of chapters that reached a
Chapter-of-Excellence award tier this cycle, an unknown and likely
small fraction of all active San Diego County SkillsUSA chapters. No
separate full chapter-directory page could be found. **Roster exists
but not usable** as a San Diego census — two named schools is too thin
and too non-representative (self-selected by an unrelated award
program, not by "did this chapter compete this year") to build a
`Team` roster from.

**11. eCyberMission.** No existing registry entry. Search surfaced one
2025-vintage San Diego team (2 named students, "E-bike Safety Patrol")
in secondary local-district coverage (`sduhsd.net`), not on any
official eCyberMission roster or results page. eCyberMission's own team
unit — 2-4 self-selected students plus an adult advisor, formed around
one project, not a standing school-affiliated group — is also a poor
structural fit for this project's per-school `Team` row shape, closer
to a one-off entered project than a standing competing team. **No
public roster exists**, and borderline on the standing-group test even
if one did.

**12. Zero Robotics.** No existing registry entry. Fetched (`curl`,
HTTP 200, 52KB) the official 2026 High School Program tournament-info
page (`zerorobotics.mit.edu/tournaments/44/info/304/0/`) directly: its
`Teams`/`Teams Leaderboard` links require "Sign in with Google" — not a
public, unauthenticated page. A secondary web-search result mentioned
"Marshall Middle School" in San Diego participating in a middle-school
cycle, but not on any citable public roster page. **Roster exists but
not usable** (real roster data lives inside MIT's authenticated
platform, not publicly fetchable).

**13. Junior Solar Sprint.** No existing registry entry. Search
surfaced only historical (pre-2020) local coverage of a San
Diego-area Junior Solar Sprint sponsored by Sullivan Solar Power at
Flora Vista Elementary; no evidence of a currently-running 2026 San
Diego program, and no roster/results page of any kind, current or
historical. **No public roster exists** (and the program's current
local existence is itself unconfirmed).

**14. Solar Cup.** No existing registry entry. Found the Metropolitan
Water District of Southern California's official Solar Cup program
page (`mwdh2o.com`), but it is an MWD-service-territory (greater
Los Angeles basin) program with no San Diego-specific results
breakout discoverable via search. **No public roster exists (not
confirmed San Diego-specific)** — the same shape as Future City.

**15. Math Circle / AMC-AIME school teams.** Already registered as an
*event* (`sd-math-circle.toml`, disabled for an unrelated
extraction-mechanism reason — its calendar-grid sheet confuses the
LLM extractor, per its own header). Checked the TOML first, then went
past the disabled calendar source to SD Math Circle's own dedicated
`/events/arml` page (fetched via `curl`, HTTP 200, 157KB): stale since
at least 2020 ("The Annual ARML Competition will be held on May 29 &
30, 2020"), naming no current students, schools, or team members.
Independent research on SDMC's ARML program structure confirms it
fields **one composite all-star team of individually-invited students**
selected from across San Diego by exam score, not a set of named
*school* teams — a structurally poorer fit for this project's
per-school `Team` row shape than MATHCOUNTS' or Science Olympiad's
per-school teams, even setting the staleness aside. **No public roster
exists** (stale page; underlying team is not school-shaped even when
current).

**16. picoCTF.** No existing registry entry. Confirmed picoCTF 2026
(March 9-19, 2026) is real and allows teams of up to 5 students, but it
is an open, self-registering online competition — any student anywhere
forms an ad hoc team — with no institutional roster, standings-by-
school page, or "which schools fielded a team" breakdown published
anywhere found. **No public roster exists**, and structurally a poor
fit for a standing "Team" row (ad hoc, not a standing school-affiliated
group), the same shape as eCyberMission.

**17. Mayor's Cyber Cup.** No existing registry entry (the program
itself has been renamed/absorbed). Found: San Diego's Mayor's Cyber Cup
is now NDIA San Diego's "SoCal Cyber Cup Challenge," a 5-county
(San Diego/Riverside/Imperial/Orange/San Bernardino) competition.
Fetched (`curl`, HTTP 200, 111KB) `https://www.ndia-sd.org/
ndiasdevents/socal-cyber-cup-challenge/` directly: the page states
explicitly that "at the end of the tournament, we will provide a list
of the 24 Finals teams to silver level and above sponsors" — the
roster exists but is deliberately gated behind a paid sponsorship
tier, never published publicly. `sdccoe.org`'s own "San Diego Mayor's
Cyber Cup" event page (fetched, HTTP 200) is a stale 2016 event
listing with no current data. **Roster exists but not usable** —
explicitly sponsor-gated, and not San-Diego-exclusive (5-county event)
even if it were obtained.

**Additional type discovered — MATE ROV Competition.** Surfaced via
adjacent SeaPerch/underwater-robotics search. No dedicated San Diego
regional could be confirmed live in `materovcompetition.org`'s
regionals directory during this bounded pass. **No public roster
exists / no confirmed San Diego regional** — flagged for a future
ticket to check `materovcompetition.org/regionals` directly once/if a
San Diego-area regional is confirmed to exist.

**Additional type discovered — Congressional App Challenge.** Already
registered as a sprint-029 event (`congressional-app-challenge-sd.toml`,
enabled, and the one source in that whole batch that currently
`wrote 1 opportunity` in a dry run). Not one of issue 47's 16, but
structurally team-shaped (teams of up to 4 students submit an app to a
named competition). Its registered page
(`congressionalappchallenge.us/participating-districts/`) lists
*participating congressional districts* (CA-49/50/51/52), not named
student teams; no separate team-level roster/winners page was located
during this bounded pass. **Not researched to roster depth this
ticket** — flagged as a candidate worth a dedicated look in a future
research ticket, out of this ticket's 16-item scope.

## Testing

- **Existing tests to run**: none — no code or data changes in this
  ticket.
- **New tests to write**: none.
- **Verification command**: N/A. Any live fetch performed as part of
  this research (checking a candidate roster page) requires
  `dangerouslyDisableSandbox: true` on the Bash tool per this project's
  standing constraint that live verification uses the real network
  even though the test suite never does.
