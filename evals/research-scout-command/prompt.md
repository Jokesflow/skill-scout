---
description: Ресёрч через команду /scout (проверяет переход scout → skill-scout).
expected_outcome: >-
  Свежие источники закрыты встроенным веб-поиском (в «Уже есть») или поисковым MCP; для научных
  статей предложен источник вроде PubMed/arXiv/Semantic Scholar или честно указано «Не найдено»;
  PDF-отчёт закрыт скиллом/плагином для PDF; не больше 5 пунктов; ничего не установлено.
tags: [research, command]
max_turns: 40
timeout_seconds: 600
allowed_tools: [Skill, Read, Glob, Grep]
---

/skill-scout:scout ресёрч рынка AI-ассистентов для юристов: свежие источники, научные статьи и итоговый отчёт в PDF
