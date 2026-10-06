# Skill Scout

Плагин для Claude Code. По описанию задачи подбирает скиллы, плагины и MCP-серверы:
проверяет, что уже установлено, ищет недостающее в маркетплейсах плагинов, официальном
реестре MCP и на GitHub, оценивает автора, свежесть и запрашиваемые права и выдаёт до
5 рекомендаций с командами установки. Сам ничего не устанавливает.

## Установка

В сессии Claude Code:

```text
/plugin marketplace add jokesflow/skill-scout
/plugin install skill-scout@skill-scout
```

Для разработки, без установки и только на одну сессию: `claude --plugin-dir ./skill-scout`.

## Как пользоваться

- **Само:** в начале новой задачи (дизайн, код, ресёрч, маркетинг, данные…) или на вопрос
  «что мне нужно для…», «какие скиллы / плагины / MCP подойдут».
- **Командой:** `/scout <описание задачи>`. Если имя `/scout` занято другим плагином —
  `/skill-scout:scout`.

При первом запуске Claude Code спросит `Use skill "skill-scout:skill-scout"?`. Так он делает
для каждого скилла с `allowed-tools`: скилл заранее разрешает себе только поиск — свой скрипт
`scout.py`, `claude plugin list`, `claude mcp list`, WebFetch к реестру MCP, GitHub и
claude.com и WebSearch. Ответьте «Yes, and don't ask again», чтобы в этом проекте он больше
не спрашивал, или разрешите скилл везде в `~/.claude/settings.json`:

```json
{ "permissions": { "allow": ["Skill(skill-scout:skill-scout)"] } }
```

Установка выбранного — только после вашего «да».

## Структура

```text
skill-scout/
├── .claude-plugin/
│   ├── plugin.json              # манифест плагина
│   └── marketplace.json         # маркетплейс из этого же репозитория: /plugin marketplace add jokesflow/skill-scout
├── skills/
│   ├── skill-scout/
│   │   ├── SKILL.md             # основной скилл: триггеры, алгоритм, формат ответа
│   │   ├── references/
│   │   │   ├── sources.md       # где искать, запасные пути, команды установки
│   │   │   └── evaluation.md    # как оценивать автора, свежесть и права
│   │   └── scripts/
│   │       └── scout.py         # поиск и проверка кандидатов (только чтение)
│   └── scout/
│       └── SKILL.md             # команда /scout <описание задачи>
├── evals/                       # кейсы для claude plugin eval
├── tests/                       # офлайн-тесты scout.py
└── README.md
```

`/scout` сделан скиллом с `disable-model-invocation: true`, а не файлом в `commands/`:
по документации Claude Code команды — устаревший формат, и для новых плагинов рекомендуют
скиллы. Основной скилл помечен `user-invocable: false`, чтобы в меню `/` была одна команда.

## Как это работает

1. **Разбор задачи:** тип, стек и сервисы, конечный результат → 2–5 потребностей и
   английские ключевые слова.
2. **Что уже есть:** скиллы и MCP-инструменты в контексте Claude, `claude plugin list`,
   `claude mcp list`, а на claude.ai и в Cowork — `ListSkills`, `ListPlugins`, `ListConnectors`.
3. **Поиск недостающего:**
   - плагины — маркетплейсы пользователя (`claude plugin list --available --json`) и каталоги
     Anthropic: `claude-plugins-official`, `claude-community`, `anthropic-agent-skills`,
     `knowledge-work-plugins`, даже если они не добавлены;
   - MCP — официальный реестр `registry.modelcontextprotocol.io` и коннекторы claude.ai;
   - скиллы и всё остальное — `SearchSkills`, GitHub.
4. **Оценка:** покрытие задачи, автор (вендор, Anthropic, сообщество, неизвестный), дата
   обновления, права: хуки, локальные и удалённые MCP-серверы, `bin/`, `allowed-tools`
   скиллов, токены и OAuth.
5. **Ответ:** «Уже есть и пригодится», «Стоит поставить» (до 5 пунктов с типом, ссылкой и
   командой), «Не найдено», вопрос, что ставить.

## Скрипт scout.py

| Команда | Что делает |
| --- | --- |
| `inventory` | Установленные плагины, MCP-серверы, скиллы в `~/.claude/skills` и `.claude/skills` |
| `plugins <kw>…` | Поиск по каталогам плагинов: тир каталога, репозиторий, команда установки |
| `mcp <kw>…` | Поиск в реестре MCP: издатель (домен или аккаунт GitHub), удалённый сервер или пакет, нужные секреты, команда `claude mcp add` |
| `github <kw>… [--kind skill\|plugin\|mcp]` | Поиск репозиториев: звёзды, последний push, лицензия |
| `inspect <name@marketplace \| github-url \| owner/repo \| папка>` | Состав плагина и права: хуки, MCP, `bin/`, `allowed-tools`, `userConfig`, звёзды и дата изменения |

Python 3.8+, только стандартная библиотека, только чтение. Переменная `GH_TOKEN` или
`GITHUB_TOKEN` поднимает лимиты GitHub API.

## Тестовые запросы

Те же запросы лежат в `evals/` как кейсы для `claude plugin eval`. Конкретные плагины
зависят от того, какие маркетплейсы и коннекторы есть у пользователя; ниже — что ожидается
и что вернули прогоны на Claude Code 2.1.291.

**1. Дизайн** — «Хочу сверстать лендинг по макету из Figma на Next.js и задеплоить его на
Vercel. Что мне для этого нужно из скиллов, плагинов и MCP?»

- Скилл срабатывает сам, без команды.
- «Уже есть»: встроенные Bash, правка файлов и генерация кода — Next.js, вёрстка, `npx vercel`.
- «Стоит поставить»: плагин **figma** от самой Figma (`github.com/figma/mcp-server-guide`,
  удалённый MCP `mcp.figma.com` и скиллы, вход через OAuth) —
  `/plugin install figma@claude-plugins-official`; для Vercel — плагин `vercel` с ⚠ «ставит
  5 хуков, которые запускают node-скрипты на каждой сессии» или более лёгкий удалённый MCP
  `claude mcp add --transport http vercel-mcp https://mcp.vercel.com`.
- «Не найдено»: отдельный инструмент для самого деплоя не нужен — хватит Vercel CLI.
- В конце вопрос «Что поставить?», ничего не установлено.

**2. Код** — «Пишу REST API на FastAPI с PostgreSQL: нужны миграции, тесты и ревью кода
перед PR. Какие скиллы, плагины или MCP-серверы мне подойдут?»

- «Уже есть»: `/code-review`, `/security-review`, Bash для Alembic и pytest — под них ничего
  не ставится.
- «Стоит поставить»: GitHub для PR и CI (`github@claude-plugins-official`, удалённый MCP, нужен
  токен), Python LSP или quality gate (например, `pyright-lsp@claude-plugins-official`), MCP
  или коннектор для своей Postgres-БД (в прогоне — коннектор Neon) с ⚠ о правах на запись и
  удаление.
- «Не найдено»: отдельного плагина под Alembic нет — миграции Claude пишет и проверяет сам.

**3. Ресёрч, через команду** — `/scout ресёрч рынка AI-ассистентов для юристов: свежие
источники, научные статьи и итоговый отчёт в PDF`

- `/scout` передаёт задачу в `skill-scout:skill-scout`.
- «Уже есть»: WebSearch и WebFetch для свежих источников, PDF-скилл, если он установлен
  (иначе — `document-skills@anthropic-agent-skills`).
- «Стоит поставить»: MCP для научных статей — например, `arxiv-mcp-server` из реестра с
  ⚠ «частный автор, локальный процесс, пишет файлы на диск»; плагин для разбора статей —
  по желанию.
- «Не найдено»: журналы по праву и SSRN — через WebSearch, проверенного MCP нет.

**Негативный кейс** — «Переименуй в этом фрагменте переменную x в total…»: скилл не
вызывается, Claude просто правит код.

## Проверки

```bash
claude plugin validate . --strict          # манифест, маркетплейс и скиллы
python3 -m unittest discover -s tests      # офлайн-тесты scout.py
claude plugin eval . --judge-model sonnet --allow-tools "Bash(python3 *)" WebSearch \
  "WebFetch(domain:registry.modelcontextprotocol.io)" \
  "WebFetch(domain:raw.githubusercontent.com)" "WebFetch(domain:api.github.com)"
```

`claude plugin eval` запускает каждый кейс 3 раза с плагином и 3 раза без него и расходует
лимиты вашего плана. Для одного прогона: `--case <имя> --runs 1 --ablation none`. Выдача
Bash в evals требует песочницы: на Linux — пакеты `bubblewrap` и `socat`. Судья по умолчанию
(haiku) на русских ответах бывает нестабилен, поэтому в команде выше — `--judge-model sonnet`.

## Ограничения

- Реестр MCP ищет только по именам серверов, поэтому в ключевые слова ставьте название
  продукта: `figma`, `postgres`, `notion`.
- GitHub API без токена — 10 поисковых запросов в минуту и 60 остальных в час; `inspect`
  тратит до трёх запросов на кандидата.
- В облачных сессиях claude.ai/code плагины, установленные на вашей машине, не загружаются.
- В Claude Code 2.1.291 в headless-режиме (`claude -p`, evals) разрешения из `allowed-tools`
  скилла не действуют на вызовы в следующих запросах модели. В интерактивной сессии они
  работают. Для `-p` передайте разрешения флагом `--allowedTools`, для evals — `--allow-tools`.
