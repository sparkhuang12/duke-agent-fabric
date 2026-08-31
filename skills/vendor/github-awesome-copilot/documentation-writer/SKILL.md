---
name: documentation-writer
description: Write software documentation using the Diataxis tutorial, how-to, reference and explanation model.
---

# Documentation Writer

This is a project-curated adaptation of GitHub's `documentation-writer` skill.

## Principles

- Clarity: use simple, direct and unambiguous language.
- Accuracy: verify commands, examples and behavior against the implementation.
- User focus: every document should help a defined audience reach a defined goal.
- Consistency: keep terminology, tone and structure stable across the project.

## Choose one primary document type

- Tutorial: a learning-oriented path that gets a newcomer to a working result.
- How-to guide: a task-oriented recipe for solving a specific problem.
- Reference: an information-oriented description of APIs, configuration or behavior.
- Explanation: an understanding-oriented discussion of architecture and trade-offs.

Do not mix all four styles into every document. Cross-link related documents instead.

## Workflow

1. Establish the document type, audience, goal, scope and explicit exclusions.
2. Inspect the current code, configuration and existing terminology.
3. Draft the smallest structure that satisfies the reader's goal.
4. Verify every command and code sample where possible.
5. Mark environment-specific assumptions and production caveats.
6. Add links to deeper reference material rather than duplicating it.

## Quality gate

- The opening paragraph says what the reader will achieve.
- Prerequisites and failure modes are explicit.
- Commands are copyable and do not embed secrets.
- Public behavior matches the current implementation.
- Headings and examples remain useful when read out of order.

