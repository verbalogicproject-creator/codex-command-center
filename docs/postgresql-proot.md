---
id: command-center.postgresql-proot
repository: Command Center
title: PostgreSQL Verification Under Ubuntu PRoot
kind: operations_guide
audience:
  - engineer
  - operator
  - ai_agent
status: verified
owner_area: persistence and deployment
main_files:
  - services/memory/aria_memory/postgres.py
  - services/memory/tests/test_postgres_behavior.py
  - services/memory/tests/test_postgres_contract.py
public_interfaces:
  - "DATABASE_URL"
  - "COMMAND_CENTER_TEST_DATABASE_URL"
  - "PostgresDatabase"
provides:
  - reproducible phone-local PostgreSQL behavioral verification
  - restart and historical-evidence test procedure
  - Cloud SQL parity gate before deployment
depends_on:
  - command-center.architecture-awareness
  - command-center.cloud-run
safe_edit_points:
  - disposable command_center_test database
  - random test-owned workspace schemas
  - loopback-only port 5433 configuration
risk_areas:
  - stale postmaster PID after an unclean proot exit
  - a daemon being reaped when the proot parent exits
  - testing against a production database
graph_rag_entities:
  - PostgresDatabase
  - PostgreSQL
  - Ubuntu PRoot
  - Cloud SQL
last_verified: 2026-07-18
---

# PostgreSQL verification under Ubuntu PRoot

Command Center uses SQLite for local development and Cloud SQL PostgreSQL for
hosted mutable workspaces. The PostgreSQL adapter must pass behavior tests, not
only SQL-string inspection.

This phone-local route reuses the verified Atlas pattern: Ubuntu under
`proot-distro`, PostgreSQL bound to `127.0.0.1:5433`, and the Termux test runner
connecting over the shared loopback network. Command Center stores embedding
vectors as portable `BYTEA`; pgvector is not required for this contract.

## Safety

Use a dedicated disposable database. Never point
`COMMAND_CENTER_TEST_DATABASE_URL` at production. Each behavioral test creates
a random `ws_<hex>` schema and drops that schema in `finally`.

The commands below assume an existing Ubuntu PostgreSQL 18 cluster at
`/var/lib/postgresql/18/main`, as documented and exercised by Atlas. For a
fresh laptop, use the distribution PostgreSQL package and port 5432 instead.

## Start the proot cluster

A PostgreSQL child is reaped when its proot parent exits, so keep the login
alive for the duration of the test:

```sh
proot-distro login ubuntu --shared-tmp -- bash -lc '
  su postgres -s /bin/bash -c \
    "/usr/lib/postgresql/18/bin/pg_ctl \
      -D /var/lib/postgresql/18/main \
      -l /var/lib/postgresql/18/main/command-center.log \
      -o \"-p 5433\" start"
  pg_isready -h 127.0.0.1 -p 5433
  tail -f /dev/null
'
```

If `pg_ctl status` says no server is running but `postmaster.pid` exists, first
confirm that `pg_isready` fails and no PostgreSQL process owns that data
directory. Only then remove the stale PID and start again.

From another Termux shell:

```sh
pg_isready -h 127.0.0.1 -p 5433
createdb -h 127.0.0.1 -p 5433 -U postgres command_center_test
```

## Install the test client without changing the project

On Termux, the pure-Python psycopg wheel can live in a temporary target:

```sh
python3 -m pip install \
  --target "$PREFIX/tmp/command-center-psycopg" \
  'psycopg>=3.2,<4'
```

The production Docker image installs the declared `postgres` extra normally.

## Run the contract

```sh
PYTHONPATH="$PREFIX/tmp/command-center-psycopg" \
COMMAND_CENTER_TEST_DATABASE_URL=\
postgresql://postgres@127.0.0.1:5433/command_center_test \
pytest -q \
  services/memory/tests/test_postgres_behavior.py \
  services/memory/tests/test_postgres_contract.py
```

The behavioral test verifies:

- application and architecture migrations;
- active-to-historical snapshot transition;
- byte-identical resolution of a historical architecture document;
- repository alias resolution;
- adapter re-instantiation as a service-restart proxy;
- retrieval of the new active ArchitectureBrief within its token budget;
- cleanup of the random workspace schema.

The 2026-07-18 first run caught a real compatibility defect:
`compat_row_factory` iterated `cursor.description` for DDL commands, where
psycopg correctly provides `None`. The adapter now treats command-only results
as having zero columns. The test passed before and after a clean PostgreSQL
stop/start.

## Stop cleanly

```sh
proot-distro login ubuntu --shared-tmp -- bash -lc '
  su postgres -s /bin/bash -c \
    "/usr/lib/postgresql/18/bin/pg_ctl \
      -D /var/lib/postgresql/18/main -m fast stop"
'
```

Then close the keepalive login. A clean stop avoids a stale PID on the next
run.

## Cloud promotion gate

Before Cloud Run promotion:

1. run the complete SQLite suite;
2. run the PostgreSQL contract above;
3. stop/start PostgreSQL and repeat the behavioral test;
4. build the production web bundle;
5. build the root Dockerfile on a Docker-capable laptop or Cloud Build;
6. run authenticated MCP initialize/list/call smoke tests against staging;
7. promote the same saved image digest to production.

Android/Termux in this workspace has no Docker engine. That is an environment
limit, not a skipped application test: container build and deployed handshake
remain explicit laptop/Cloud Build gates.
