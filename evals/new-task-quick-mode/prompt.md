---
description: Quick mode. A direct task, not a "what do I need" question, should still trigger skill-scout first.
expected_outcome: >-
  skill-scout runs before the work in quick mode: it names what is already available (for example
  a pptx skill) and what would help (a way to read Google Sheets, a way to post to Slack), each
  with how to install or connect it, then asks before installing or connecting anything.
tags: [quick-mode, english]
max_turns: 40
timeout_seconds: 600
allowed_tools: [Skill, Read, Glob, Grep]
---

Build a quarterly sales deck in PowerPoint from our Google Sheets pipeline data and post a summary to our Slack #sales channel.
