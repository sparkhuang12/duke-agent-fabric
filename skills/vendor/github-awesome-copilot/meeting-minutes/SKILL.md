---
name: meeting-minutes
description: Generate concise and actionable meeting minutes with decisions, owners, due dates, evidence and follow-up steps.
---

# Meeting Minutes

This is a project-curated adaptation of GitHub's `meeting-minutes` skill.

## Purpose

Produce factual meeting minutes that prioritize decisions, accountable action items and traceable source material. Never turn an implication into a confirmed decision.

## Intake

Before drafting, identify:

- title, date, duration, organizer and intended audience;
- agenda, transcript, recording or raw notes;
- designated reviewer or approver.

If critical details are absent, mark them `TBD`. Do not invent attendees, owners, dates or decisions.

## Output schema

Use the following structure:

1. Metadata
   - Title
   - Date and duration
   - Organizer
   - Location
   - Author and distribution list
2. Attendance
   - Present
   - Absent
   - Recorder
3. Agenda
4. Executive summary
5. Decisions
   - Decision
   - Approver
   - Rationale
   - Effective date
   - Source timestamp or note reference
6. Action items
   - ID
   - Action
   - Owner
   - Due date or timeframe
   - Acceptance criteria
   - Linked artifact
7. Notes by agenda item
8. Unresolved items
9. Risks and blockers
10. Next meeting or follow-up
11. Attachments and references
12. Version and change log

## Quality rules

- Every action item needs an owner and due date; otherwise use `TBD` and identify who must confirm it.
- Significant decisions need a short rationale and a source reference.
- Separate facts, opinions and unresolved questions.
- Avoid speculative or unverified claims.
- Do not expose personal or sensitive information unless required and authorized.
- Use ISO 8601 dates.
- Keep the result concise and suitable for human review.

## Acceptance checklist

- Metadata, attendance, decisions and action items are present.
- Every action item is testable and attributable.
- Uncertain information is labeled.
- Source material is referenced or explicitly listed as unavailable.
- A reviewer is named or marked `TBD`.

