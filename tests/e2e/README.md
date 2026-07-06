# Tests

End-to-end coverage for the actions, run by [`.github/workflows/test.yml`](../../.github/workflows/test.yml).

## `e2e-deploy`

A sanity check that the `deploy` action can actually deploy to a real Connect:

1. [`posit-dev/with-connect`](https://github.com/posit-dev/with-connect) starts a
   Connect container in start-only mode and exposes its server URL and API key.
2. Two content records are created via the Connect API (the `deploy` action
   *updates* existing content, so the records must exist first).
3. A manifest is generated for the [`fastapi-app`](fastapi-app) fixture, then the
   `deploy` action runs several times:
   - `draft: false` (production), via the `manifest.json` path;
   - again on the same record *without* a manifest, so it exercises the other
     `deploy.sh` branch — query Connect for `app_mode` (`posit connect api`), map
     it to a `posit connect deploy` subcommand, and deploy;
   - once more from a `pyproject.toml` + `uv.lock` copy, exercising
     `generate-requirements.sh`'s lockfile-export branch;
   - `draft: true` (preview), on the draft-capable legs.
4. The job verifies each deploy set a non-empty `content-url`, that the URL is a
   draft URL only for the draft deploy, and that bundles were uploaded.

A freshly created content record has an `app_mode` of `unknown`, so the deploys go
through the action's `manifest.json` path — the one path that takes a brand-new
record straight to deployed without looking up the app type from Connect.

The workflow's own steps talk to Connect through `posit connect api`, which reads
`CONNECT_SERVER` / `CONNECT_API_KEY` from the environment, so no login is needed.

### Prerequisite

The workflow needs a Posit Connect license file stored as the `CONNECT_LICENSE`
secret (the file contents, following the `with-connect` convention). Without it the
Connect container will not start.

The suite runs against a matrix of Connect versions (`fail-fast: false`) to catch
version-specific regressions and enforce the supported range:

- **`2024.12.0`** — older than every version-gated feature (draft previews,
  metadata, OIDC). Asserts the baseline still works: a plain API-key production
  deploy. The draft and cleanup legs are skipped (`supports-drafts: false`).
- **`2025.07.0`** — the floor for working draft previews. Metadata is still silently skipped (needs
  2025.12.0) but the deploy succeeds.
- **`2025.12.0`** — the metadata floor; the full suite runs with git provenance
  metadata.
- **`release`** — the latest Connect build, to surface breakage early.

The deploy action reads the server version and degrades gracefully where a
feature is missing, so the older legs pass without it rather than failing.

### Running

It runs automatically on pull requests and on pushes to `main`, and can be
triggered manually from the Actions tab (`workflow_dispatch`).
