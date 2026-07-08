# Contributing

Thanks for your interest! This repo is a collection of Claude Code skills, one
per subdirectory under `skills/`.

## Setup

```bash
git clone https://github.com/sandypoli-boop/sansheng-skills.git
cd sansheng-skills
git config core.hooksPath .githooks   # enable the redact-guard pre-commit hook
```

## Adding or changing a skill

- Each skill lives in `skills/<name>/` with its own `SKILL.md` (the skill
  definition, with a `name` + `description` frontmatter) and a short `README.md`.
- Keep secrets out of the code: read keys from environment variables and ship a
  `.env.example` (names only). Read data paths from an env var, not a hard-coded
  absolute path.
- If a skill has tests, run them before opening a PR (e.g. `pytest` inside the
  skill's `scripts/` directory).

## Pull requests

- Keep each PR focused on one skill / one change.
- Fill in the PR template checklist.
- The maintainer reviews and versions releases (single semver version for the
  whole repo).

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
