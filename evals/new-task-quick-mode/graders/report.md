---
type: llm
---

Judge the reply's content, not its exact formatting.

Context: the user directly asked Claude to build a quarterly sales deck in PowerPoint from
Google Sheets pipeline data and post a summary to Slack. A tool-scouting step should run first,
in a quick mode, before the work starts.

PASS if all of these are true:
1. Before doing the work, the reply covers the tools this task needs — a way to read the
   Google Sheets data, a way to post to Slack and a way to build the .pptx — as already
   available, as recommendations, or under "Not found" with a workaround. Alternatively it says
   in one line that no extra tools are needed and continues.
2. Every numbered recommendation says what kind of tool it is and how to install or connect it.
3. It asks the user before installing or connecting anything and never says that Claude already
   installed or connected something.

Otherwise FAIL. Clarifying questions about the task, warnings and notes never cause a FAIL on
their own.
