# Contributing

Thanks for helping. skill-scout is small on purpose: one skill, one command and one
dependency-free helper script.

## Set up

```bash
git clone https://github.com/Jokesflow/skill-scout
cd skill-scout
claude --plugin-dir .        # loads the plugin for one session, nothing is installed
```

## Before you open a pull request

```bash
claude plugin validate . --strict          # manifest, marketplace and skills
python3 -m unittest discover -s tests      # offline tests, no network
```

If you changed a `SKILL.md`, its `description` or the output format, also run the affected
eval cases (see the README) and check that the negative case still doesn't trigger.

## Ground rules

- `scout.py` stays read-only and uses the Python 3.8+ standard library only.
- Nothing in the plugin installs, enables or connects anything. That is always the user's call.
- A new data source needs a fallback in `skills/skill-scout/references/sources.md` and a test
  built on a captured fixture. Tests never touch the network.
- Keep `SKILL.md` under 500 lines; move detail into `references/`.
- Recommendations must come from tool output. Never hard-code plugin names, links or commands
  into the skill as "known good".

## Reporting a bad recommendation

Open an issue with the "Bad recommendation" template: the prompt, what skill-scout suggested,
and what was wrong with it. Remove tokens and private details first.
