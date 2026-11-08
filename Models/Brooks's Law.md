---
type: model
domain: systems
origin_year: 1975
status: new
aliases: [Brooks' Law]
---

## What it is
"Adding manpower to a late software project makes it later." New people cost time before they save any, and coordination grows faster than headcount, so staffing up a late project can push it further behind.

## Origin
Fred Brooks stated it in *The Mythical Man-Month* (1975), drawing on his years managing IBM's System/360 and its OS/360 operating system in the 1960s. He presented it as a deliberate, outrageous oversimplification of a real tendency, not a precise law.

## Why it works
- **Ramp-up:** newcomers need training from the experienced staff who were doing the work, so output drops before it rises.
- **Communication overhead:** possible pairwise channels grow roughly with the square of team size. Three people have 3 channels; ten have 45.
- **Indivisible tasks:** some work cannot be split. Brooks's example: more women do not shorten a nine-month pregnancy.

## Best used when
- A project is already late and the proposed fix is more people.
- Work is tightly coupled and depends on shared context.
- Little time remains relative to how long newcomers take to become productive.

## Limitations
It is a rule of thumb, not a measured result. Steve McConnell argued in 1999 that it mainly bites when people join near the end, and that many projects are later than they look because the estimate was wrong. Simulation studies suggest added staff reliably raise cost but only sometimes extend the schedule. Experienced hires and early additions blunt it.

## Avoid when
- Work divides into independent pieces, like a backlog of support tickets.
- New people bring missing skills and need little onboarding.

## Counter-models and tensions
- [[Division of Labour]]: for divisible work, more hands genuinely finish sooner.
- [[Planning Fallacy]]: many "late" projects were never on schedule to begin with, so the real problem is the estimate, not the headcount.

## Who used it
- IBM's OS/360, the project that taught Brooks the lesson.
- Commentators invoked it during the troubled 2013 launch of HealthCare.gov, when extra engineers were drafted in to rescue the site.

## Trigger question
Will the next person shorten the remaining work, or lengthen it while they learn?

## Often confused with
- [[Sunk Cost Fallacy]], which is about refusing to stop, not adding staff.
- [[Conway's Law]], which links a team's communication structure to what it builds.
- [[Parkinson's Law]], about work expanding to fill time rather than people slowing it.

## Go deeper
- [Brooks, The Mythical Man-Month, Anniversary Edition (Pearson)](https://www.pearson.com/en-us/subject-catalog/p/mythical-man-month-the-essays-on-software-engineering/P200000007221/9780201835953)
- [Martin Fowler, MythicalManMonth](https://martinfowler.com/bliki/MythicalManMonth.html)

## Recall
#flashcards
A software release is three weeks late and the director assigns six new engineers to finish it. What is the likely result?::Later still: [[Brooks's Law]], as ramp-up and coordination costs swamp the extra hands. [[Division of Labour]] would win only if the remaining work split cleanly.
A warehouse doubles its pickers before peak season and throughput nearly doubles. Why did adding people work here?::[[Division of Labour]]: picking splits into independent tasks with little shared context. [[Brooks's Law]] bites on coupled, already-late work, not on this.
A project slips for the fourth time and the manager asks for two more engineers. What two explanations should be weighed first?::The [[Planning Fallacy]]: the estimate may have been wrong all along, not the staffing. Adding people anyway invites [[Brooks's Law]].
