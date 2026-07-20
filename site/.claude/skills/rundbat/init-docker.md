# init-docker

Scaffold a `docker/` directory for the project. Produces a self-contained
deployment package: Dockerfile, docker-compose.yml, Justfile, and
.env.example.

## When to use

- "Set up Docker for this project"
- "Containerize this app"
- "I need a compose file"

## Prerequisites

- Project initialized (`rundbat.yaml` exists — run `rundbat init` first)

## Steps

1. Run the generator:
   ```bash
   rundbat init-docker --json
   ```

   This auto-detects the framework and generates all artifacts.

2. Review the generated files in `docker/`:
   - `Dockerfile` — framework-specific multi-stage build
   - `docker-compose.yml` — app + database services with health checks
   - `Justfile` — deployment recipes (build, up, down, deploy, db ops)
   - `.env.example` — environment variable template

3. Test locally:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

## Generated Justfile recipes

- `just build` — build the app image
- `just up` / `just down` — compose lifecycle
- `just deploy` — deploy via `rundbat deploy`
- `just logs` — tail service logs
- `just psql` / `just mysql` — database shell (if applicable)
- `just db-dump` / `just db-restore` — database backup/restore

## Outputs

```
docker/
  Dockerfile
  docker-compose.yml
  .env.example
  Justfile
```
