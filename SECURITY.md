# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Email
**sandypoli@gmail.com** with details and I'll respond as soon as I can.

## For contributors

These skills call external APIs and touch local files. When you contribute:

- **Never commit real API keys, tokens, or passwords.** Read them from
  environment variables / a git-ignored `.env`; the repo ships only
  `.env.example` (variable names, no values).
- A `pre-commit` redact-guard (`.githooks/pre-commit`) scans staged changes
  for common key formats and personal paths. Activate it once per clone:
  `git config core.hooksPath .githooks`.
- Don't commit book files or other copyrighted source material -- keep them in
  your git-ignored data directory (`distill-data/`).
