#!/usr/bin/env python3
"""skill-scout helper: find and vet skills, plugins and MCP servers for a task.

Read-only. It searches catalogs and registries and prints short summaries.
It never installs, enables or configures anything.

Usage:
  scout.py inventory                        installed plugins, MCP servers, local skills
  scout.py plugins KEYWORD [KEYWORD ...]    search plugin marketplaces (registered + Anthropic's)
  scout.py mcp KEYWORD [KEYWORD ...]        search the official MCP Registry
  scout.py github KEYWORD [...] [--kind K]  search GitHub repositories (K: skill, plugin, mcp, any)
  scout.py inspect TARGET                   components, permissions and freshness of one candidate.
                                            TARGET: name@marketplace, GitHub URL, owner/repo[/path],
                                            MCP Registry name (com.example/server) or a local directory

Keywords are case-insensitive substrings; terms of three letters or fewer match whole words.
Use English keywords: product names first (figma, postgres), then capabilities (design, scraping).
Stdlib only, Python 3.8+. Set GH_TOKEN or GITHUB_TOKEN to raise GitHub API rate limits.
"""

import argparse
import concurrent.futures
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "skill-scout/0.1 (+https://github.com/Jokesflow/skill-scout)"
TIMEOUT = 15
REGISTRY = "https://registry.modelcontextprotocol.io/v0.1"
GITHUB_API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
GITHUB_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
GITHUB_NAME = r"[A-Za-z0-9._-]+"
SAFE_REF = re.compile(r"^[A-Za-z0-9._/-]+$")

# Anthropic catalogs searched even when the user hasn't added them: (marketplace name, GitHub repo).
KNOWN_CATALOGS = [
    ("claude-plugins-official", "anthropics/claude-plugins-official"),
    ("claude-community", "anthropics/claude-plugins-community"),
    ("anthropic-agent-skills", "anthropics/skills"),
    ("knowledge-work-plugins", "anthropics/knowledge-work-plugins"),
]
# Marketplace names Claude Code reserves for Anthropic (official and community tiers).
OFFICIAL_MARKETPLACES = {
    "claude-plugins-official", "claude-code-marketplace", "claude-code-plugins",
    "anthropic-marketplace", "anthropic-plugins", "agent-skills", "anthropic-agent-skills",
    "life-sciences", "knowledge-work-plugins", "claude-for-legal", "claude-for-financial-services",
    "financial-services-plugins", "first-party-plugins", "claude-tag-plugins",
}
COMMUNITY_MARKETPLACES = {"claude-community", "claude-plugins-community", "healthcare"}
DIRECTORY_MARKETPLACES = {"anthropic-plugin-directory", "claude-plugin-directory"}


def marketplace_tier(name):
    if name in OFFICIAL_MARKETPLACES:
        return "official marketplace"
    if name in DIRECTORY_MARKETPLACES:
        return "Anthropic directory"
    if name in COMMUNITY_MARKETPLACES:
        return "community marketplace"
    return "third-party marketplace"


class FetchError(Exception):
    pass


# --------------------------------------------------------------------------- helpers

def short(text, limit=170):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def day(stamp):
    return (stamp or "")[:10] or "?"


def warn(message):
    print("! " + message)


def fetch(url, accept="application/json", github_auth=False, timeout=TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if github_auth and token:
        # Unredirected: the token never follows a redirect to another host.
        request.add_unredirected_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        detail = ""
        try:
            detail = json.loads(err.read().decode("utf-8", "replace")).get("message", "")
        except Exception:
            pass
        raise FetchError("HTTP %d%s" % (err.code, ": " + short(detail, 120) if detail else ""))
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as err:
        raise FetchError(short(getattr(err, "reason", None) or err, 120) or "network error")


def fetch_json(url, **kwargs):
    text = fetch(url, **kwargs)
    try:
        return json.loads(text)
    except ValueError:
        raise FetchError("not JSON: " + short(text, 80))


def cache_dir():
    """A per-user cache folder: $XDG_CACHE_HOME, %LOCALAPPDATA% on Windows, else ~/.cache."""
    base = os.environ.get("XDG_CACHE_HOME") or (os.environ.get("LOCALAPPDATA") if os.name == "nt" else None)
    return os.path.join(base or os.path.join(os.path.expanduser("~"), ".cache"), "skill-scout")


def owned(path):
    """True when the current user owns the path; always True where the OS has no uids."""
    if not hasattr(os, "getuid"):
        return True
    try:
        return os.stat(path).st_uid == os.getuid()
    except OSError:
        return False


def cached_fetch(url, ttl=24 * 3600, fresh=False):
    """Public catalog files, cached for a day in a folder only the current user owns."""
    folder = cache_dir()
    path = os.path.join(folder, re.sub(r"[^A-Za-z0-9]+", "_", url)[-150:])
    try:
        if not fresh and owned(folder) and owned(path) and time.time() - os.path.getmtime(path) < ttl:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
    except OSError:
        pass
    text = fetch(url)
    try:
        os.makedirs(folder, mode=0o700, exist_ok=True)
        if owned(folder):
            with open(path + ".tmp", "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(path + ".tmp", path)
    except OSError:
        pass
    return text


def sh(word):
    """Quote a word for the shell unless it is plain, so placeholders such as <TOKEN> stay text
    instead of becoming redirections."""
    word = str(word)
    if re.match(r"^[A-Za-z0-9_@%+=:,./-]+$", word):
        return word
    return '"%s"' % re.sub(r'(["\\$`])', r"\\\1", word)


def run_claude(args, timeout=90):
    exe = shutil.which("claude")
    if not exe:
        raise FetchError("the claude CLI is not on PATH")
    try:
        proc = subprocess.run([exe] + args, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as err:
        raise FetchError(short(err, 120))
    if proc.returncode != 0:
        raise FetchError(short(proc.stderr or proc.stdout, 160) or "exit %d" % proc.returncode)
    return proc.stdout


def parallel(func, items):
    """Run func over items in threads; returns [(item, result, error)] in input order."""
    def call(item):
        try:
            return item, func(item), None
        except FetchError as err:
            return item, None, err
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(8, len(items)))) as pool:
        return list(pool.map(call, items))


def terms_of(keywords):
    terms = []
    for word in keywords:
        word = word.strip().lower()
        if word and word not in terms:
            terms.append(word)
    return terms


def hit(term, text):
    if len(term) <= 3:
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None
    return term in text


def score(terms, name, text):
    """(number of matched terms, points). A match in the name weighs more than in the text."""
    name, text = (name or "").lower(), (text or "").lower()
    matched = points = 0
    for term in terms:
        in_name, in_text = hit(term, name), hit(term, text)
        if in_name or in_text:
            matched += 1
            points += (3 if in_name else 0) + (1 if in_text else 0)
    return matched, points


def github_repo(url):
    """owner/repo for a github.com URL or owner/repo shorthand, else None."""
    match = re.match(r"^(?:https?://(?:www\.)?github\.com/|git@github\.com:)?"
                     r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", (url or "").strip())
    return "%s/%s" % match.groups() if match else None


def frontmatter(text):
    """Tiny YAML-frontmatter reader: top-level `key: value` pairs, folded values joined."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    data, key = {}, None
    for line in text[3:end if end != -1 else len(text)].splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            data[key] = "" if value in (">", "|", ">-", "|-", ">+", "|+") else value.strip("'\"")
        elif key and line[:1] in (" ", "\t"):
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


# --------------------------------------------------------------------------- inventory

def cmd_inventory(_args):
    print("Installed plugins (claude plugin list):")
    try:
        data = json.loads(run_claude(["plugin", "list", "--json"]))
        rows = data.get("installed", []) if isinstance(data, dict) else data
        for row in rows:
            state = "enabled" if row.get("enabled") else "disabled"
            print("  - %s  v%s  %s, %s" % (row.get("id"), row.get("version", "?"), row.get("scope", "?"), state))
        if not rows:
            print("  (none)")
    except (FetchError, ValueError) as err:
        warn("plugin list unavailable: %s" % err)

    print("MCP servers (claude mcp list):")
    try:
        lines = [line for line in run_claude(["mcp", "list"], timeout=120).splitlines()
                 if line.strip() and not line.startswith("Checking")]
        for line in lines[:40]:
            print("  " + short(line, 160))
    except FetchError as err:
        warn("mcp list unavailable: %s" % err)

    print("Skills in skills directories:")
    found = False
    for base in (os.path.join(os.path.expanduser("~"), ".claude", "skills"),
                 os.path.join(os.getcwd(), ".claude", "skills")):
        if not os.path.isdir(base):
            continue
        for entry in sorted(os.listdir(base)):
            skill_md = os.path.join(base, entry, "SKILL.md")
            if os.path.isfile(skill_md):
                try:
                    with open(skill_md, encoding="utf-8", errors="replace") as handle:
                        meta = frontmatter(handle.read(4000))
                except OSError:
                    meta = {}
                print("  - %s: %s" % (meta.get("name") or entry, short(meta.get("description"), 110)))
                found = True
    if not found:
        print("  (none)")
    print("Note: skills from plugins and claude.ai, and connected MCP tools (mcp__<server>__*), "
          "are listed in Claude's own context; treat that list as the source of truth.")


# --------------------------------------------------------------------------- plugins

def origin_of(source, catalog_repo=None, catalog_dir=None):
    """Where a plugin's files live: {'repo', 'path', 'ref'} on GitHub, plus 'local' when the
    marketplace is cloned on disk, or {'other': text}."""
    if isinstance(source, str):
        path = source[2:] if source.startswith("./") else source
        path = "" if path in (".", "") else path.strip("/")
        if ".." in path.split("/"):
            return {"other": source}
        local = os.path.join(catalog_dir, *path.split("/")) if catalog_dir and path else catalog_dir
        if not catalog_repo and not local:
            return {"other": source}
        return {"repo": catalog_repo, "path": path, "ref": None, "local": local}
    if not isinstance(source, dict):
        return {"other": "?"}
    kind, ref = source.get("source"), source.get("sha") or source.get("ref")
    if kind == "github" and source.get("repo"):
        return {"repo": source["repo"], "path": "", "ref": ref}
    if kind in ("url", "git-subdir"):
        repo = github_repo(source.get("url", ""))
        path = str(source.get("path") or "").strip("/")
        if repo and ".." not in path.split("/"):
            return {"repo": repo, "path": path, "ref": ref}
        return {"other": source.get("url", "?")}
    if kind == "npm":
        return {"other": "npm:" + str(source.get("package"))}
    return {"other": str(kind)}


def origin_text(origin):
    if origin.get("repo"):
        return "github.com/%s%s" % (origin["repo"], "/" + origin["path"] if origin["path"] else "")
    return origin.get("local") or origin.get("other", "?")


def count_text(number):
    return "%.1fk" % (number / 1000.0) if number >= 1000 else str(number)


def load_catalogs():
    """Returns (entries, installed ids, registered marketplace names, notes)."""
    entries, installed, registered, notes = [], set(), set(), []
    markets, known = {}, dict(KNOWN_CATALOGS)
    try:
        for row in json.loads(run_claude(["plugin", "marketplace", "list", "--json"])):
            if isinstance(row, dict) and row.get("name"):
                markets[row["name"]] = row
                registered.add(row["name"])
    except (FetchError, ValueError, TypeError):
        pass
    try:
        data = json.loads(run_claude(["plugin", "list", "--available", "--json"]))
        if isinstance(data, list):
            data = {"installed": data, "available": []}
        for row in data.get("installed", []):
            installed.add(row.get("id"))
        for row in data.get("available", []):
            market = row.get("marketplaceName")
            info = markets.get(market, {})
            repo = info.get("repo") or github_repo(info.get("url", "")) or known.get(market)
            location = info.get("installLocation")
            registered.add(market)
            entries.append({
                "id": row.get("pluginId"), "name": row.get("name"), "market": market,
                "description": row.get("description") or "", "version": row.get("version"),
                "installs": row.get("installCount"), "registered": True,
                "origin": origin_of(row.get("source"), repo, location if location and os.path.isdir(location) else None)})
    except (FetchError, ValueError) as err:
        notes.append("registered marketplaces unavailable (%s); searching Anthropic catalogs only" % err)

    missing = [(name, repo) for name, repo in KNOWN_CATALOGS if name not in registered]

    def load(item):
        name, repo = item
        url = "%s/%s/HEAD/.claude-plugin/marketplace.json" % (RAW, repo)
        for fresh in (False, True):  # a cached copy that no longer parses is fetched again
            try:
                data = json.loads(cached_fetch(url, fresh=fresh))
                if isinstance(data, dict):
                    return data
            except ValueError:
                pass
        raise FetchError("bad catalog JSON")

    for (name, repo), data, err in parallel(load, missing):
        if err:
            notes.append("catalog %s unavailable: %s" % (name, err))
            continue
        for row in data.get("plugins", []):
            author = row.get("author") if isinstance(row.get("author"), dict) else {}
            entries.append({
                "id": "%s@%s" % (row.get("name"), name), "name": row.get("name"), "market": name,
                "description": row.get("description") or "", "version": row.get("version"),
                "origin": origin_of(row.get("source"), repo), "registered": False,
                "author": author.get("name"), "homepage": row.get("homepage"), "add": repo})
    return entries, installed, registered, notes


def plugin_score(terms, entry):
    name = (entry["name"] or "").lower()
    matched, points = score(terms, name, name + " " + entry["description"])
    tokens = set(re.split(r"[^a-z0-9]+", name))
    owner = (entry["origin"].get("repo") or "").split("/")[0].lower()
    for term in terms:
        if term == name or (term in tokens and len(tokens) <= 2):
            points += 3  # the plugin is named after the term, e.g. "figma"
        if owner and term == owner:
            points += 4  # published by the vendor itself, e.g. github.com/figma/...
    if owner == "anthropics":
        points += 2
    if entry["market"] in OFFICIAL_MARKETPLACES:
        points += 1
    if len(entry["description"].strip()) < 25:
        points -= 4  # placeholder or test listing
    return matched, points


def cmd_plugins(args):
    terms = terms_of(args.keywords)
    entries, installed, registered, notes = load_catalogs()
    for note in notes:
        warn(note)
    ranked = []
    for entry in entries:
        matched, points = plugin_score(terms, entry)
        if matched:
            ranked.append((-matched, -points, not entry["registered"], entry["id"], entry))
    ranked.sort(key=lambda row: row[:4])

    shown, seen = [], {}
    for row in ranked:
        entry = row[4]
        key = (entry["name"], origin_text(entry["origin"]))
        primary = seen.get(key)
        if primary is None:
            entry["also"] = []
            seen[key] = entry
            shown.append(entry)
        elif entry["registered"] and not primary["registered"]:
            # Same plugin in a marketplace the user already has: show that copy, it installs in one step.
            entry["also"] = primary["also"] + [primary["market"]]
            for field in ("author", "homepage"):
                entry.setdefault(field, primary.get(field))
            shown[shown.index(primary)] = seen[key] = entry
        else:
            primary["also"].append(entry["market"])
    total = len(shown)
    shown = shown[: args.limit]

    print("Plugins matching %s: %d found, top %d. Registered marketplaces: %s" % (
        ", ".join(terms), total, len(shown), ", ".join(sorted(m for m in registered if m)) or "none"))
    for number, entry in enumerate(shown, 1):
        flags = []
        if entry["id"] in installed:
            flags.append("INSTALLED")
        if not entry["registered"]:
            flags.append("marketplace not added")
        head = "%2d. %s%s · %s%s%s · %s" % (
            number, entry["id"], "  [" + ", ".join(flags) + "]" if flags else "", marketplace_tier(entry["market"]),
            " · v" + entry["version"] if entry.get("version") else "",
            " · %s installs" % count_text(entry["installs"]) if isinstance(entry.get("installs"), int) else "",
            origin_text(entry["origin"]))
        print(head)
        print("    " + short(entry["description"]))
        extra = []
        if entry.get("author"):
            extra.append("author: " + entry["author"])
        if entry.get("homepage"):
            extra.append(entry["homepage"])
        if entry["also"]:
            extra.append("also in: " + ", ".join(sorted(set(entry["also"]))))
        if extra:
            print("    " + " · ".join(extra))
        if entry["id"] not in installed:
            if entry["registered"]:
                print("    install: /plugin install %s" % entry["id"])
            else:
                print("    install: /plugin marketplace add %s, then /plugin install %s" % (entry["add"], entry["id"]))
    if not shown:
        print("  nothing matched; try a product name or a broader capability word")


# --------------------------------------------------------------------------- MCP registry

def official_meta(item):
    meta = item.get("_meta") or {}
    return meta.get("io.modelcontextprotocol.registry/official") or {}


# Hosting platforms that hand out subdomains to anyone: proving one says nothing about a vendor.
SHARED_HOSTS = ("vercel.app", "netlify.app", "github.io", "pages.dev", "workers.dev", "herokuapp.com",
                "onrender.com", "fly.dev", "railway.app", "web.app", "firebaseapp.com", "azurewebsites.net",
                "appspot.com", "glitch.me", "replit.app", "deno.dev", "ngrok.app", "ngrok.io", "run.app")


def publisher(name):
    """Registry names prove who published them: io.github.<login>/* needs that GitHub login,
    any other reverse-DNS namespace needs DNS or HTTP proof of the domain."""
    namespace = name.split("/", 1)[0]
    if namespace.lower().startswith("io.github."):
        return "github", namespace[len("io.github."):]
    domain = ".".join(reversed(namespace.split(".")))
    if any(domain.lower() == host or domain.lower().endswith("." + host) for host in SHARED_HOSTS):
        return "shared", domain
    return "domain", domain


def publisher_text(kind, who):
    return {"github": "GitHub account " + who,
            "shared": who + " (subdomain of a shared host, not a vendor domain)"}.get(kind, "verified domain " + who)


def mcp_label(name):
    namespace, _, tail = name.partition("/")
    tail = tail.lower()
    if tail and tail not in ("mcp", "server", "mcp-server", "remote", "mcp-remote", "api"):
        label = tail
    else:
        parts = [p for p in namespace.lower().split(".") if p not in (
            "com", "io", "ai", "dev", "app", "org", "net", "co", "github", "mcp", "www", "so", "sh")]
        label = parts[0] if parts else namespace.lower()
    return re.sub(r"[^a-z0-9_-]+", "-", label).strip("-") or "mcp-server"


def placeholders(text):
    """Registry values reference user input as {name} or ${name}; show them as <name>."""
    return re.sub(r"\$?\{([A-Za-z0-9_.-]+)\}", r"<\1>", str(text))


def package_args(arguments):
    """Registry argument specs as shell words: fixed values, and required ones as placeholders."""
    words = []
    for arg in arguments or []:
        if not isinstance(arg, dict):
            continue
        value = arg.get("value") or arg.get("default")
        if not value and not arg.get("isRequired"):
            continue
        value = placeholders(value) if value else "<%s>" % (arg.get("valueHint") or arg.get("name") or "value")
        if arg.get("type") == "named" and arg.get("name"):
            words.append(sh(arg["name"]))
        words.append(sh(value))
    return words


RUNNERS = {"npm": "npx", "pypi": "uvx", "oci": "docker"}
DEFAULT_REGISTRIES = ("https://registry.npmjs.org", "https://pypi.org", "https://docker.io")


def mcp_install_lines(server):
    """Install commands built only from registry metadata, plus notes on what they can't cover."""
    label, lines = mcp_label(server.get("name", "")), []
    for remote in server.get("remotes") or []:
        transport = {"streamable-http": "http", "sse": "sse"}.get(remote.get("type"))
        if not transport or not remote.get("url"):
            continue
        headers = ["--header " + sh("%s: <%s>" % (h.get("name"), h.get("name")))
                   for h in remote.get("headers") or [] if isinstance(h, dict) and h.get("isRequired")]
        lines.append("install: claude mcp add --transport %s %s %s%s" % (
            transport, label, sh(placeholders(remote["url"])), " " + " ".join(headers) if headers else ""))
    for package in server.get("packages") or []:
        if not isinstance(package, dict) or (package.get("transport") or {}).get("type", "stdio") != "stdio":
            continue
        kind, ident, version = package.get("registryType"), package.get("identifier"), package.get("version")
        if kind not in RUNNERS or not ident:
            continue
        envs = [e.get("name") for e in package.get("environmentVariables") or []
                if isinstance(e, dict) and e.get("isRequired") and e.get("name")]
        runtime = package_args(package.get("runtimeArguments"))
        if kind == "npm":
            command = ["npx"] + ([] if {"-y", "--yes"} & set(runtime) else ["-y"]) + runtime
            command.append(sh("%s@%s" % (ident, version) if version else ident))
        elif kind == "pypi":
            command = ["uvx"] + runtime + [sh("%s@%s" % (ident, version) if version else ident)]
        else:
            command = ["docker", "run", "-i", "--rm"] + ["-e " + sh(n) for n in envs] + runtime + [sh(ident)]
        command += package_args(package.get("packageArguments"))
        env_flags = "".join(" -e " + sh("%s=<%s>" % (n, n)) for n in envs)
        lines.append("install: claude mcp add %s%s -- %s" % (label, env_flags, " ".join(command)))
        hint, base = package.get("runtimeHint"), package.get("registryBaseUrl")
        if hint and hint != RUNNERS[kind]:
            lines.append("note: the registry suggests running it with %s; check the README" % hint)
        if base and not base.rstrip("/").startswith(DEFAULT_REGISTRIES):
            lines.append("note: the package comes from %s, not the default registry" % base)
    return lines


def describe_server(server, meta, number=None):
    head = "%s%s%s · v%s · updated %s%s" % (
        "%2d. " % number if number else "", server.get("name"),
        " — " + server["title"] if server.get("title") else "", server.get("version", "?"),
        day(meta.get("updatedAt") or meta.get("publishedAt")),
        "" if meta.get("status", "active") == "active" else " · STATUS " + str(meta.get("status")).upper())
    print(head)
    print("    " + short(server.get("description")))
    links = [x for x in ((server.get("repository") or {}).get("url"), server.get("websiteUrl")) if x]
    print("    publisher: %s%s" % (publisher_text(*publisher(server.get("name", ""))),
                                   " · " + " · ".join(links) if links else ""))
    for remote in server.get("remotes") or []:
        heads = [h.get("name") + (" (secret)" if h.get("isSecret") else "")
                 for h in remote.get("headers") or [] if h.get("isRequired")]
        print("    remote %s: %s%s" % (remote.get("type"), remote.get("url"),
                                        " · needs header " + ", ".join(heads) if heads else ""))
    for package in server.get("packages") or []:
        envs = ["%s%s" % (e.get("name"), " (secret)" if e.get("isSecret") else "")
                for e in package.get("environmentVariables") or [] if e.get("isRequired")]
        parts = [package.get("registryType"), package.get("identifier"), package.get("version"),
                 "(%s)" % (package.get("transport") or {}).get("type", "stdio")]
        print("    package %s%s" % (" ".join(str(p) for p in parts if p),
                                    " · needs env " + ", ".join(envs) if envs else ""))
    for line in mcp_install_lines(server):
        print("    " + line)


def cmd_mcp(args):
    terms = terms_of(args.keywords)

    def search(term):
        query = urllib.parse.urlencode({"search": term, "limit": 50, "version": "latest"})
        return fetch_json("%s/servers?%s" % (REGISTRY, query)).get("servers", [])

    servers, failed = {}, []
    for term, found, err in parallel(search, terms):
        if err:
            failed.append("%s (%s)" % (term, err))
            continue
        for item in found:
            server = item.get("server") or {}
            if server.get("name") and official_meta(item).get("status") != "deleted":
                servers[server["name"]] = (server, official_meta(item))
    if failed:
        warn("MCP Registry search failed for: " + "; ".join(failed) +
             ". Fall back to WebSearch/WebFetch, the claude.ai connector directory or GitHub.")

    ranked = []
    for server, meta in servers.values():
        matched, points = score(terms, server["name"] + " " + server.get("title", ""),
                                server.get("description", ""))
        kind, who = publisher(server["name"])
        labels = who.lower().split(".")
        if kind == "domain" and len(labels) >= 2 and labels[-2] in terms:
            points += 4  # the service's own domain published it, e.g. com.figma.mcp -> mcp.figma.com
        if matched:
            inactive = meta.get("status", "active") != "active"
            updated = int(re.sub(r"\D", "", meta.get("updatedAt") or "")[:8] or 0)
            ranked.append((inactive, -matched, -points, -updated, server["name"], server, meta))
    ranked.sort(key=lambda row: row[:5])
    print("MCP Registry (registry.modelcontextprotocol.io) matching %s: %d found, top %d. "
          "The registry searches server names only." % (", ".join(terms), len(ranked), min(len(ranked), args.limit)))
    for number, row in enumerate(ranked[: args.limit], 1):
        describe_server(row[5], row[6], number)
    if not ranked and not failed:
        print("  nothing matched; try the product or service name (e.g. figma, postgres, notion)")


# --------------------------------------------------------------------------- GitHub search

def cmd_github(args):
    hint = {"skill": "claude skill", "plugin": "claude plugin", "mcp": "mcp server", "any": ""}[args.kind]
    words = ['"%s"' % k if " " in k else k for k in args.keywords]
    query = " ".join(words + ([hint] if hint else []) + ["fork:false", "archived:false"])
    url = "%s/search/repositories?%s" % (GITHUB_API, urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": args.limit}))
    try:
        data = fetch_json(url, github_auth=True)
    except FetchError as err:
        warn("GitHub search failed (%s). Set GH_TOKEN/GITHUB_TOKEN, or use WebSearch with site:github.com." % err)
        return
    items = data.get("items", [])
    print("GitHub repositories for [%s]: %s total, top %d by stars" % (query, data.get("total_count", "?"), len(items)))
    for number, repo in enumerate(items, 1):
        license_id = (repo.get("license") or {}).get("spdx_id") or "no license"
        print("%2d. %s ★%s · pushed %s · %s · owner %s" % (
            number, repo.get("full_name"), repo.get("stargazers_count"), day(repo.get("pushed_at")),
            license_id, (repo.get("owner") or {}).get("type", "?")))
        print("    " + short(repo.get("description")))
        print("    " + str(repo.get("html_url")))


# --------------------------------------------------------------------------- inspect

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mcpb-cache"}
MAX_LOCAL_FILES = 20000
MAX_DOCS = 60


def check_github(repo, ref=None):
    """Refuse repository names and refs that could be read as options or break a URL."""
    if not re.match(r"^%s/%s$" % (GITHUB_OWNER, GITHUB_NAME), repo or ""):
        raise FetchError("not a GitHub repository name: %r" % repo)
    if ref and (ref.startswith("-") or ".." in ref or not SAFE_REF.match(ref)):
        raise FetchError("refusing a suspicious git ref: %r" % ref)


def git_listing(repo, ref, path):
    """File list and commit date of one revision, fetched without file contents (no API quota)."""
    check_github(repo, ref)
    git = shutil.which("git")
    if not git:
        raise FetchError("git is not installed")
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    with tempfile.TemporaryDirectory(prefix="skill-scout-") as tmp:
        def run(*args):
            try:
                proc = subprocess.run([git, "-C", tmp] + list(args), capture_output=True, text=True,
                                      timeout=60, env=env, encoding="utf-8", errors="replace")
            except (OSError, subprocess.TimeoutExpired) as err:
                raise FetchError(short(err, 120))
            if proc.returncode != 0:
                raise FetchError(short(proc.stderr, 160) or "git failed")
            return proc.stdout
        run("init", "-q")
        run("fetch", "-q", "--depth", "1", "--filter=blob:none", "--",
            "https://github.com/%s.git" % repo, ref or "HEAD")
        names = run("ls-tree", "-r", "--name-only", "FETCH_HEAD", "--", path or ".").splitlines()
        date = run("log", "-1", "--format=%cI", "FETCH_HEAD").strip()
    prefix = path + "/" if path else ""
    return [name[len(prefix):] for name in names if name.startswith(prefix)], date


class Source:
    """Read files of a plugin that lives on GitHub, on the local disk, or both
    (a marketplace clone on disk whose repository is known)."""

    def __init__(self, repo=None, path="", ref=None, local=None):
        if repo:
            check_github(repo, ref)
        self.repo, self.path, self.ref, self.local = repo, (path or "").strip("/"), ref, local
        self.files = None  # relative paths under the plugin root, when a listing is available

    def label(self):
        remote = "github.com/%s%s%s" % (self.repo, "/" + self.path if self.path else "",
                                        " @ " + self.ref[:12] if self.ref else "") if self.repo else ""
        if self.local:
            return self.local + (" (" + remote + ")" if remote else "")
        return remote

    def list_files(self):
        if self.local:
            out = []
            for root, dirs, names in os.walk(self.local):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                out.extend(os.path.relpath(os.path.join(root, name), self.local).replace(os.sep, "/")
                           for name in sorted(names))
                if len(out) >= MAX_LOCAL_FILES:
                    warn("stopped listing after %d files; component counts may be incomplete" % MAX_LOCAL_FILES)
                    break
            self.files = out
            return
        prefix = self.path + "/" if self.path else ""
        try:
            tree = fetch_json("%s/repos/%s/git/trees/%s?recursive=1" % (GITHUB_API, self.repo, self.ref or "HEAD"),
                              github_auth=True)
        except FetchError as api_err:
            try:
                self.files, date = git_listing(self.repo, self.ref, self.path)
            except FetchError as git_err:
                raise FetchError("GitHub API: %s; git: %s" % (api_err, git_err))
            print("Revision date (git): %s" % day(date))
            return
        self.files = sorted(item["path"][len(prefix):] for item in tree.get("tree", [])
                            if isinstance(item, dict) and item.get("type") == "blob"
                            and str(item.get("path", "")).startswith(prefix))
        if tree.get("truncated"):
            warn("file listing truncated by GitHub; component counts may be incomplete")

    def has(self, rel):
        return None if self.files is None else rel in self.files

    def read(self, rel):
        """File text, or None when it doesn't exist."""
        if self.has(rel) is False:
            return None
        if self.local:
            try:
                with open(os.path.join(self.local, rel), encoding="utf-8", errors="replace") as handle:
                    return handle.read()
            except OSError:
                return None
        full = "/".join(x for x in (self.path, rel) if x)
        try:
            return fetch("%s/%s/%s/%s" % (RAW, self.repo, self.ref or "HEAD", urllib.parse.quote(full)),
                         accept="*/*")
        except FetchError as err:
            if str(err).startswith("HTTP 404"):
                return None
            raise


def resolve_target(target):
    """Returns (Source or None, registry server name or None)."""
    target = target.strip()
    if os.path.isdir(target):
        return Source(local=os.path.abspath(target)), None
    if target.startswith((".", "/", "~", "\\")) or re.match(r"^[A-Za-z]:[\\/]", target):
        raise FetchError("no such directory: %s" % target)
    if "@" in target and "/" not in target:
        entries, _installed, _registered, notes = load_catalogs()
        for note in notes:
            warn(note)
        entry = next((e for e in entries if e["id"] == target), None)
        if not entry:
            raise FetchError("%s not found in registered or Anthropic catalogs" % target)
        origin = entry["origin"]
        print("%s · %s" % (entry["id"], short(entry["description"], 140)))
        if origin.get("local") and os.path.isdir(origin["local"]):
            return Source(origin.get("repo"), origin["path"], None, local=origin["local"]), None
        if not origin.get("repo"):
            raise FetchError("%s is not hosted on GitHub (%s); review it manually" % (target, origin.get("other")))
        return Source(origin["repo"], origin["path"], origin["ref"]), None
    if re.match(r"^(?:https?://)?(?:www\.)?github\.com/", target, re.I):
        match = re.match(r"^(?:https?://)?(?:www\.)?github\.com/(%s)/([A-Za-z0-9._-]+?)(?:\.git)?"
                         r"(?:/(?:tree|blob)/([^/?#]+)/?([^?#]*))?/?(?:[?#].*)?$" % GITHUB_OWNER, target, re.I)
        if not match:
            raise FetchError("not a GitHub repository URL: %s" % target)
        owner, name, ref, path = match.groups()
        return Source("%s/%s" % (owner, name), (path or "").strip("/"), ref), None
    if re.match(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/[^/\s]+$", target):
        return None, target  # reverse-DNS MCP Registry name, e.g. com.figma.mcp/mcp
    match = re.match(r"^(%s)/(%s)(?:/(.+))?$" % (GITHUB_OWNER, GITHUB_NAME), target.strip("/"))
    if match:
        return Source("%s/%s" % (match.group(1), match.group(2)), match.group(3) or ""), None
    raise FetchError("can't interpret %r: use name@marketplace, a GitHub URL, owner/repo[/path], "
                     "an MCP Registry name or a local directory" % target)


def repo_health(repo, path, ref):
    try:
        info = fetch_json("%s/repos/%s" % (GITHUB_API, repo), github_auth=True)
    except FetchError as err:
        warn("repository metadata unavailable (%s); check stars/license/activity on the GitHub page" % err)
        return
    owner = info.get("owner") if isinstance(info.get("owner"), dict) else {}
    print("Repo: github.com/%s · ★%s · owner %s (%s) · %s · last push %s%s" % (
        repo, info.get("stargazers_count"), owner.get("login"), owner.get("type"),
        (info.get("license") or {}).get("spdx_id") or "no license",
        day(info.get("pushed_at")), " · ARCHIVED" if info.get("archived") else ""))
    query = {"per_page": 1}
    if path:
        query["path"] = path
    if ref:
        query["sha"] = ref
    try:
        commits = fetch_json("%s/repos/%s/commits?%s" % (GITHUB_API, repo, urllib.parse.urlencode(query)),
                             github_auth=True)
        if commits:
            print("Last change%s: %s" % (" to " + path if path else "",
                                          day(commits[0]["commit"]["committer"]["date"])))
    except (FetchError, KeyError, IndexError, TypeError):
        pass


def summarize_hooks(data, where):
    lines = []
    if not isinstance(data, dict):
        return ["⚠ %s is not a JSON object; review it by hand" % where]
    if data.get("modules"):
        modules = data["modules"] if isinstance(data["modules"], list) else [data["modules"]]
        lines.append("⚠ mod (JavaScript inside Claude Code with fs/process/http access): %s in %s"
                     % (", ".join(map(str, modules)), where))
    events = data.get("hooks", data)
    for event, groups in (events.items() if isinstance(events, dict) else []):
        if event == "modules" or not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks") or []:
                if not isinstance(hook, dict):
                    continue
                action = str(hook.get("command") or hook.get("url") or hook.get("prompt") or "")
                if isinstance(hook.get("args"), list):
                    action += " " + " ".join(map(str, hook["args"]))
                line = "⚠ hook %s[%s] %s: %s" % (event, group.get("matcher") or "*",
                                                hook.get("type", "?"), short(action, 110))
                if line not in lines:
                    lines.append(line)
    if len(lines) > 8:
        lines = lines[:8] + ["⚠ … and %d more hooks in %s" % (len(lines) - 8, where)]
    return lines


def summarize_mcp(data, where):
    lines = []
    servers = data.get("mcpServers", data) if isinstance(data, dict) else {}
    for name, cfg in (servers.items() if isinstance(servers, dict) else []):
        if not isinstance(cfg, dict):
            continue
        supplied = {}
        for key in ("env", "headers"):
            if isinstance(cfg.get(key), dict):
                supplied.update(cfg[key])
        secrets = sorted(key for key, value in supplied.items() if not value or "${" in str(value))
        needs = " · needs " + ", ".join(secrets) if secrets else ""
        if cfg.get("url"):
            lines.append("• remote MCP %s (%s): %s%s — data goes to this service"
                         % (name, cfg.get("type", "http"), cfg["url"], needs))
        else:
            args = cfg.get("args") if isinstance(cfg.get("args"), list) else []
            command = " ".join([str(cfg.get("command", "?"))] + [str(a) for a in args])
            lines.append("⚠ local MCP %s: %s%s — runs as a process with your user rights"
                         % (name, short(command, 100), needs))
    return lines


# allowed-tools rules that amount to "run anything" or "write anywhere".
INTERPRETERS = {"bash", "sh", "zsh", "fish", "dash", "ksh", "pwsh", "powershell", "cmd", "python", "python3",
                "py", "node", "deno", "bun", "ruby", "perl", "php", "osascript"}
EXECUTORS = {"npx", "uvx", "bunx", "pnpx"}
MANAGERS = {"npm", "pnpm", "yarn", "uv", "pip", "pip3", "pipx", "cargo", "go", "docker", "podman", "make",
            "gradle", "mvn"}
WRAPPERS = {"sudo", "env", "xargs", "eval", "exec", "nohup", "timeout", "nice", "watch", "curl", "wget", "ssh"}
INLINE_FLAGS = {"-c", "-e", "--eval", "-m", "-", "-p", "--print", "-r", "-command", "-encodedcommand", "/c"}
RUN_VERBS = {"run", "exec", "x", "dlx", "install", "i", "add", "start"}
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def grant_rules(value):
    """allowed-tools as (tool, pattern) pairs, whether written as a string, a YAML list or JSON."""
    text = re.sub(r"[\"'\[\]]", " ", str(value))
    text = re.sub(r"(^|\s)-(?=\s|$)", " ", text)
    return [(m.group(1), (m.group(2) or "").strip())
            for m in re.finditer(r"([A-Za-z_][\w.:-]*)(?:\(([^)]*)\))?", text)]


def broad_rule(tool, pattern):
    if tool in FILE_TOOLS:
        return not pattern or bool(re.match(r"^[/~*]*$", pattern.replace("\\", "/")))
    if tool not in ("Bash", "PowerShell"):
        return False
    words = pattern.replace(":*", " *").split()
    if not words or all(set(word) <= {"*"} for word in words):
        return True
    program = re.split(r"[\\/]", words[0])[-1].lower()
    program = program[:-4] if program.endswith(".exe") else program
    args = words[1:]
    if program not in INTERPRETERS | EXECUTORS | MANAGERS | WRAPPERS:
        return False
    if not args or "*" in args[0]:
        return True
    if program in INTERPRETERS and args[0].lower() in INLINE_FLAGS:
        return True
    if program in EXECUTORS:
        rest = [a for a in args if not a.startswith("-")]
        return not rest or "*" in rest[0]
    if program in INTERPRETERS | MANAGERS and args[0] in RUN_VERBS:
        return len(args) < 2 or "*" in args[1]
    return False


def broad_grants(value):
    return ["%s(%s)" % (tool, pattern) if pattern else tool
            for tool, pattern in grant_rules(value) if broad_rule(tool, pattern)]


def grant_line(where, value):
    broad = broad_grants(value)
    return "%s %s pre-approves tools: %s%s" % ("⚠" if broad else "•", where, short(value, 80),
                                                " (broad: %s)" % ", ".join(broad) if broad else "")


MISSING = object()


def read_json(src, rel):
    """Parsed JSON file of the plugin, MISSING when absent, or the string 'unreadable'."""
    text = src.read(rel)
    if text is None:
        return MISSING
    try:
        return json.loads(text)
    except ValueError:
        return "unreadable"


def declared(manifest, key):
    value = manifest.get(key)
    return value if isinstance(value, list) else [value] if value else []


def norm(path):
    return re.sub(r"^\./", "", str(path)).strip("/")


def under(path, root):
    return not root or path == root or path.startswith(root + "/")


def inspect_plugin(src):
    try:
        src.list_files()
    except FetchError as err:
        warn("file listing unavailable (%s); checking the well-known files only" % err)
    if src.files is not None and not src.files:
        warn("no files at %s: a wrong path, or the marketplace keeps its plugins elsewhere" % src.label())
        return 1

    manifest = read_json(src, ".claude-plugin/plugin.json")
    if manifest is MISSING:
        manifest = read_json(src, "plugin.json")
    if manifest is MISSING:
        manifest = {}
    elif not isinstance(manifest, dict):
        warn("plugin.json is not a JSON object; checking the default locations only")
        manifest = {}
    if manifest:
        author = manifest.get("author") if isinstance(manifest.get("author"), dict) else {}
        print("Manifest: %s v%s · author %s · license %s%s" % (
            manifest.get("name"), manifest.get("version", "?"), author.get("name", "?"),
            manifest.get("license", "?"), " · %s" % manifest["homepage"] if manifest.get("homepage") else ""))
        options = manifest.get("userConfig") if isinstance(manifest.get("userConfig"), dict) else {}
        if options:
            print("Asks the user for: " + ", ".join(
                "%s%s" % (key, " (sensitive)" if isinstance(value, dict) and value.get("sensitive") else "")
                for key, value in options.items()))
        deps = declared(manifest, "dependencies")
        if deps:
            print("Also installs dependencies: " + ", ".join(
                str(d.get("name")) if isinstance(d, dict) else str(d) for d in deps))

    files = src.files or []
    skill_roots = ["skills"] + [norm(p) for p in declared(manifest, "skills") if isinstance(p, str)]
    skill_md = [re.compile(r"^%s(?:[^/]+/)?SKILL\.md$" % (re.escape(root) + "/" if root else ""))
                for root in skill_roots]
    skill_files = sorted({f for f in files if any(p.match(f) for p in skill_md)})
    skills = sorted({f.split("/")[-2] if "/" in f else "(root)" for f in skill_files})

    spec, command_files, inline = manifest.get("commands"), [], []
    if isinstance(spec, dict):  # an object map replaces commands/
        command_roots = []
        for name, entry in spec.items():
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("source"), str):
                command_files.append(norm(entry["source"]))
            if entry.get("allowedTools"):
                tools = entry["allowedTools"]
                inline.append(("plugin.json commands.%s" % name,
                               " ".join(map(str, tools)) if isinstance(tools, list) else str(tools)))
    else:
        command_roots = [norm(p) for p in declared(manifest, "commands") if isinstance(p, str)] or ["commands"]
    commands = sorted({f for f in files if f.endswith(".md")
                       and (f in command_files or any(under(f, r) for r in command_roots))})
    agent_roots = [norm(p) for p in declared(manifest, "agents") if isinstance(p, str)] or ["agents"]
    agents = sorted({f for f in files if f.endswith(".md") and any(under(f, r) for r in agent_roots)})
    binaries = [f for f in files if f.startswith("bin/")]
    code = [f for f in files if re.search(r"\.(sh|py|js|mjs|cjs|ts|ps1|rb|go)$", f)]
    if src.files is not None:
        print("Components: %d skills%s, %d commands, %d agents, %d bundled code files" % (
            len(skills), " (" + ", ".join(skills[:12]) + ("…" if len(skills) > 12 else "") + ")" if skills else "",
            len(commands), len(agents), len(code)))

    risks = []
    for kind, default, summarize in (("hooks", "hooks/hooks.json", summarize_hooks),
                                     ("mcpServers", ".mcp.json", summarize_mcp)):
        for item in [default] + declared(manifest, kind):
            if isinstance(item, dict):
                risks += summarize(item, "plugin.json")
                continue
            rel = norm(item)
            if not rel.endswith(".json"):
                risks.append("⚠ %s from %s (bundle or URL; review it by hand)" % (kind, item))
                continue
            data = read_json(src, rel)
            if data == "unreadable":
                risks.append("⚠ %s present but unreadable" % rel)
            elif data is not MISSING:
                risks += summarize(data, rel)

    experimental = manifest.get("experimental") if isinstance(manifest.get("experimental"), dict) else {}
    if src.read(".lsp.json") or manifest.get("lspServers"):
        risks.append("⚠ LSP server: starts a language-server process")
    if binaries:
        risks.append("⚠ bin/: %d executables added to the Bash PATH (%s)" % (len(binaries), ", ".join(binaries[:5])))
    if src.has("monitors/monitors.json") or experimental.get("monitors"):
        risks.append("⚠ monitors: background shell commands")

    docs = sorted(set(skill_files) | set(commands))
    if len(docs) > MAX_DOCS:
        warn("checked %d of %d skill and command files for pre-approved tools and hooks" % (MAX_DOCS, len(docs)))
    for rel, text, err in parallel(src.read, docs[:MAX_DOCS]):
        if err or not text:
            continue
        meta = frontmatter(text)
        tools = meta.get("allowed-tools") or meta.get("allowed_tools")
        if tools:
            risks.append(grant_line(rel, tools))
        if "hooks" in meta:
            risks.append("⚠ %s registers hooks while it runs (frontmatter hooks)" % rel)
    risks += [grant_line(where, tools) for where, tools in inline]

    risks = list(dict.fromkeys(risks))  # the same file can be both the default and declared
    print("Permissions and reach:")
    for line in risks:
        print("  " + line)
    if not risks:
        if src.files is None:
            print("  no hooks/.mcp.json/.lsp.json found; bin/ and skill tool grants unknown without a file listing")
        elif not (manifest or skill_files or commands or agents):
            print("  ? no plugin.json, skills, commands or agents here; is this the plugin's root folder?")
        else:
            print("  ✓ nothing runs on its own: no hooks, MCP/LSP servers or bin/ executables%s" % (
                "; its %d bundled scripts run only through Claude's Bash calls" % len(code) if code else ""))
    return 0


def cmd_inspect(args):
    try:
        src, server_name = resolve_target(args.target)
    except FetchError as err:
        warn(str(err))
        return 1
    if server_name:
        try:
            item = fetch_json("%s/servers/%s/versions/latest" % (REGISTRY, urllib.parse.quote(server_name, safe="")))
        except FetchError as err:
            warn("MCP Registry lookup failed: %s" % err)
            return 1
        server = item.get("server") or item
        describe_server(server, official_meta(item))
        repo = github_repo((server.get("repository") or {}).get("url", ""))
        if repo:
            repo_health(repo, "", None)
        return 0
    print("Source: " + src.label())
    if src.repo:
        repo_health(src.repo, src.path, src.ref)
    try:
        return inspect_plugin(src)
    except FetchError as err:
        warn("could not read plugin files: %s" % err)
    except (AttributeError, TypeError, KeyError, ValueError) as err:
        warn("malformed plugin files (%s: %s); review them by hand" % (type(err).__name__, short(err, 100)))
    return 1


# --------------------------------------------------------------------------- main

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(prog="scout.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory", help="installed plugins, MCP servers and local skills")
    for name, default in (("plugins", 10), ("mcp", 8)):
        cmd = sub.add_parser(name, help="search " + name)
        cmd.add_argument("keywords", nargs="+")
        cmd.add_argument("-n", "--limit", type=int, default=default)
    cmd = sub.add_parser("github", help="search GitHub repositories")
    cmd.add_argument("keywords", nargs="+")
    cmd.add_argument("--kind", choices=("skill", "plugin", "mcp", "any"), default="any")
    cmd.add_argument("-n", "--limit", type=int, default=8)
    cmd = sub.add_parser("inspect", help="components, permissions and freshness of one candidate")
    cmd.add_argument("target")
    args = parser.parse_args(argv)
    handler = {"inventory": cmd_inventory, "plugins": cmd_plugins, "mcp": cmd_mcp,
               "github": cmd_github, "inspect": cmd_inspect}[args.command]
    try:
        return handler(args) or 0
    except BrokenPipeError:  # the reader stopped early, e.g. `| head`; not an error
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
