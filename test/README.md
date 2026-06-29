# Tests

End-to-end coverage for the actions, run by [`.github/workflows/test.yml`](../.github/workflows/test.yml).

## `e2e-deploy`

A sanity check that the `deploy` action can actually deploy to a real Connect:

1. [`posit-dev/with-connect`](https://github.com/posit-dev/with-connect) starts a
   Connect container in start-only mode and exposes its server URL and API key.
2. Two content records are created via the Connect API (the `deploy` action
   *updates* existing content, so the records must exist first).
3. A manifest is generated for the [`fastapi-app`](e2e/fastapi-app) fixture, then the
   `deploy` action deploys it twice: once with `draft: false` (production) and once
   with `draft: true` (preview).
4. The job verifies each deploy set a non-empty `content-url`, that the URL is a
   draft URL only for the draft deploy, and that a bundle was uploaded.

A freshly created content record has an `app_mode` of `unknown`, so the deploys go
through the action's `manifest.json` path — the one path that takes a brand-new
record straight to deployed without looking up the app type from Connect.

The draft deploy passes `--no-verify` because a brand-new record has no active
bundle for rsconnect's post-deploy check to reach; the job's own bundle/URL checks
are the real assertion there.

### Prerequisite

The workflow needs a Posit Connect license file stored as the `CONNECT_LICENSE`
secret (the file contents, following the `with-connect` convention). Without it the
Connect container will not start.

### Running

It runs automatically on pull requests and on pushes to `main`, and can be
triggered manually from the Actions tab (`workflow_dispatch`).
