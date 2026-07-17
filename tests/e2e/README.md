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
   - twice more with **no** explicit `connect-server`/`content-guid`, resolving
     both from a deployment TOML — once auto-detected from
     `.posit/publish/deployments/` (tier 3, the "commit the Posit Publisher TOML"
     workflow) and once named via the `deployment-file` input from a non-default
     location (tier 2). Both use the manifest-free app copy so the resolved
     `entrypoint` is actually used. (The resolution logic and its error cases —
     zero/multiple TOMLs, missing file — are unit-tested in
     [`tests/test_config.py`](../test_config.py) and
     [`tests/test_cli.py`](../test_cli.py).)
   - `draft: true` (preview), on the draft-capable legs.
4. A separate [`quarto-doc`](quarto-doc) fixture (a minimal `.qmd` with Python
   content) exercises the Quarto path against its own content record:
   - first via a generated `manifest.json` (the manifest-free record starts as
     `app_mode` `unknown`), which also sets the record's `app_mode` to
     `quarto-static`;
   - then again *without* a manifest, driven by a deployment TOML whose
     `type = "quarto-static"`. This is the leg that covers the Quarto-specific
     action code: the TOML type makes config resolution report a `quarto`
     `content_type` (triggering the action's "Set up Quarto" step), and
     `deploy.sh` maps `quarto-static` to the `quarto` subcommand and passes the
     resolved entrypoint as the positional document argument (Quarto has no
     `--entrypoint` flag).
5. The job verifies each deploy set a non-empty `content-url`, that the URL is a
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
