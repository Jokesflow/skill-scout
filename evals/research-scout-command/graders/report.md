---
type: llm
---

The reply is in Russian. Judge its content, not its language or exact formatting.

Context: the user ran "/scout research of the AI-assistant market for lawyers: fresh sources,
scientific papers and a final PDF report". The recommendations are the numbered items under
the «Стоит поставить» heading.

PASS if all of these are true:
1. Each of the three needs — fresh web sources, scientific papers, producing a PDF — is covered
   by something already available (for example built-in web search or a PDF skill), by a
   recommendation, or named under «Не найдено» with a reason.
2. Every numbered recommendation says what kind of tool it is (skill, plugin, MCP or
   connector), gives a URL or a catalog location, and gives an install command or a connect step.
3. There are at most 5 numbered recommendations.
4. The reply asks the user which items to install and never says that Claude already
   installed something.

Otherwise FAIL. Extra notes, warnings or a trailing list of sources never cause a FAIL on
their own.
