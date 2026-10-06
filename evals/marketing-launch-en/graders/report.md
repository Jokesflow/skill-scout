---
type: llm
---

Judge the reply's content, not its exact formatting.

Context: the user is launching a SaaS product and needs social media posts, an SEO audit of the
landing page and a weekly analytics report; they asked which skills, plugins or MCP servers to
set up. The recommendations are the numbered items under the "Worth installing" heading.

PASS if all of these are true:
1. The reply is written in English.
2. Each of the three needs — social posts, an SEO audit, an analytics report — is covered by
   something already available, by a recommendation, or named under "Not found" with a reason.
3. Every numbered recommendation says what kind of tool it is (skill, plugin, MCP or
   connector), gives a URL or a catalog location, and gives an install command or a connect step.
4. There are at most 5 numbered recommendations, and the reply asks the user which to install
   without saying that Claude already installed something.

Otherwise FAIL. Extra notes, warnings or a trailing list of sources never cause a FAIL on
their own.
