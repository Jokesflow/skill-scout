---
type: llm
---

The reply is in Russian. Judge its content, not its language or exact formatting.

Context: the user asked which skills, plugins and MCP servers they need to build a landing
page from a Figma design with Next.js and deploy it to Vercel. The recommendations are the
numbered items under the «Стоит поставить» heading.

PASS if all of these are true:
1. A Figma tool (a Figma plugin, the Figma MCP server or the Figma connector) is recommended
   or listed as already available.
2. Every numbered recommendation says what kind of tool it is (skill, plugin, MCP or
   connector), gives a URL or a catalog location, and gives an install command or a connect step.
3. There are at most 5 numbered recommendations.
4. After the recommendations the reply asks the user which items to install, and it never
   says that Claude already installed something.

Otherwise FAIL. Extra notes, warnings, a «Не найдено» section or a trailing list of sources
never cause a FAIL on their own.
