# Источники, запасные пути и команды установки

## Что уже установлено

| Что | Где смотреть |
| --- | --- |
| Скиллы | Список скиллов в твоём контексте; `ListSkills`; `~/.claude/skills/*/SKILL.md` и `.claude/skills/*/SKILL.md` |
| Плагины | `claude plugin list --json`; `ListPlugins`; вкладка Installed в `/plugin` |
| MCP-серверы | Инструменты `mcp__<server>__*` в контексте; `claude mcp list`; `ListConnectors` |

Коннекторы, добавленные на claude.ai, автоматически доступны в Claude Code, если вход
выполнен тем же аккаунтом claude.ai. В `/mcp` они называются `claude.ai <Name>`.

## Плагины

- **Добавленные маркетплейсы:** `claude plugin list --available --json` — поля `pluginId`,
  `description`, `version`, `source`.
- **Каталоги Anthropic**, даже если не добавлены. Файл каталога:
  `https://raw.githubusercontent.com/<repo>/HEAD/.claude-plugin/marketplace.json`.

  | Маркетплейс | Репозиторий | Что внутри |
  | --- | --- | --- |
  | `claude-plugins-official` | `anthropics/claude-plugins-official` | Плагины Anthropic и партнёров. В интерактивном терминале добавляется сам |
  | `claude-community` | `anthropics/claude-plugins-community` | Сторонние плагины, присланные авторами |
  | `anthropic-agent-skills` | `anthropics/skills` | `document-skills` (docx, xlsx, pptx, pdf), `example-skills` |
  | `knowledge-work-plugins` | `anthropics/knowledge-work-plugins` | marketing, design, data, sales, legal, finance и др. |

- **Веб-каталог:** https://claude.com/marketplace/plugins
- **claude.ai и Cowork:** `SearchPlugins` — каталог аккаунта и организации. Возвращает
  `author`, `publisher.tier`, `components`, `reach`.

## MCP-серверы

- **Официальный реестр:**
  `GET https://registry.modelcontextprotocol.io/v0.1/servers?search=<name>&version=latest&limit=50`.
  Ищет подстроку в имени сервера, не в описании. Карточка сервера:
  `GET /v0.1/servers/<urlencoded name>/versions/latest`.
- **Имя показывает издателя:** `io.github.<login>/…` опубликовал аккаунт GitHub `<login>`;
  `com.<vendor>.…/…` — владелец домена `<vendor>.com`, подтверждённого через DNS или HTTP.
- **Коннекторы claude.ai:** `SearchMcpRegistry` — поля `installState`, `connected`,
  список инструментов. Подключаются в Settings → Connectors.
- Многие MCP-серверы поставляются внутри плагинов (figma, notion, linear, sentry…),
  поэтому ищи их и среди плагинов.

## Скиллы

- `SearchSkills` на claude.ai.
- `anthropics/skills`: `/plugin marketplace add anthropics/skills`, затем
  `/plugin install document-skills@anthropic-agent-skills`.
- GitHub: `scout.py github <kw> --kind skill` или WebSearch `site:github.com SKILL.md <kw>`.

## GitHub

- Поиск: `GET https://api.github.com/search/repositories?q=<kw> fork:false archived:false&sort=stars`.
  Без токена — 10 запросов в минуту, с `GH_TOKEN` или `GITHUB_TOKEN` — больше.
- Репозиторий: `GET /repos/<owner>/<repo>` (`stargazers_count`, `pushed_at`, `license`,
  `archived`, `owner.type`). Последнее изменение папки:
  `GET /repos/<owner>/<repo>/commits?path=<dir>&per_page=1`.
- Файлы без API: `https://raw.githubusercontent.com/<owner>/<repo>/<ref или HEAD>/<path>`.

## Если источник недоступен

- **Реестр MCP не отвечает:** `SearchMcpRegistry`, плагины с MCP внутри, GitHub, WebSearch
  `"<product> MCP server"`. В ответе отметь, что реестр проверить не удалось.
- **Лимит GitHub API:** WebSearch `site:github.com …`, WebFetch страницы репозитория. Права
  проверь по файлам `.claude-plugin/plugin.json`, `hooks/hooks.json`, `.mcp.json` через
  raw.githubusercontent.com.
- **Нет python или shell:** WebFetch по адресам выше.
- **Ничего не нашлось:** раздел «Не найдено», без догадок.

## Команды установки

| Что ставим | Команда |
| --- | --- |
| Плагин из добавленного маркетплейса | `/plugin install <name>@<marketplace>`; в shell — `claude plugin install <name>@<marketplace>` (`--scope user` по умолчанию, `project`, `local`), затем `/reload-plugins` |
| Маркетплейс | `/plugin marketplace add <owner/repo>` или `claude plugin marketplace add <owner/repo>` |
| Удалённый MCP | `claude mcp add --transport http <name> <url>`; с токеном — `--header "Authorization: Bearer <token>"`; OAuth — потом `/mcp` или `claude mcp login <name>` |
| Локальный MCP из npm | `claude mcp add <name> -e KEY=<value> -- npx -y <package>@<version>` |
| Локальный MCP из PyPI | `claude mcp add <name> -- uvx <package>@<version>` |
| Локальный MCP в Docker | `claude mcp add <name> -- docker run -i --rm <image>` |

Scope для MCP: `local` по умолчанию (только этот проект, только у тебя), `user` (все твои
проекты), `project` (файл `.mcp.json` в репозитории, для всей команды).
