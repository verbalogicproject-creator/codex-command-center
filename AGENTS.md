# Command Center v3 contributor guide

Keep the public demo corpus synthetic and sanitized. Never commit `.env` files,
SQLite databases, prompts, access codes, API keys, or local absolute paths.

Run before handoff:

```sh
pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
```

The memory row schema remains version 1. App schema changes use the independent
`app_migrations` table. Model-facing code may only create pending proposals;
only the authenticated confirmation endpoint may mutate durable memory.

