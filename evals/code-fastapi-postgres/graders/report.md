---
type: llm
---

The reply is in Russian. Judge its content, not its language or exact formatting.

Context: the user builds a REST API with FastAPI and PostgreSQL (migrations, tests, code
review before a PR) and asked which skills, plugins or MCP servers fit. The recommendations
are the numbered items under the «Стоит поставить» heading.

PASS if all of these are true:
1. A PostgreSQL or database tool (an MCP server, a connector or a plugin) is recommended, listed
   as already available, or named under «Не найдено» with a reason.
2. A code-quality tool (code review, a Python language server, linting or testing) is
   recommended or listed as already available.
3. Every numbered recommendation says what kind of tool it is (skill, plugin, MCP or
   connector), gives a URL or a catalog location, and gives an install command or a connect step.
4. There are at most 5 numbered recommendations, and after them the reply asks the user which
   to install without saying that Claude already installed something.

Otherwise FAIL. Extra notes, warnings or a trailing list of sources never cause a FAIL on
their own.
