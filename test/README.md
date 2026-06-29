# Tests

End-to-end coverage for the actions, run by [`.github/workflows/test.yml`](../.github/workflows/test.yml).

## `e2e-deploy`

A sanity check that the `deploy` action can actually deploy to a real Connect:

1. [`posit-dev/with-connect`](https://github.com/posit-dev/with-connect) starts a
   Connect container in start-only mode and exposes its server URL and API key.
2. A content record is created via the Connect API (the `deploy` action *updates*
   existing content, so the record must exist first).
3. A manifest is generated for the [`fastapi-app`](e2e/fastapi-app) fixture and the
   `deploy` action deploys it to that record.
4. The job verifies the action set a non-empty `content-url` and that a bundle was
   uploaded to the content.

A freshly created content record has an `app_mode` of `unknown`, so the deploy goes
through the action's `manifest.json` path — the one path that takes a brand-new
record straight to deployed without looking up the app type from Connect.

### Prerequisite

The workflow needs a Posit Connect license file stored as the `CONNECT_LICENSE`
secret (the file contents, following the `with-connect` convention). Without it the
Connect container will not start.

### Running

It runs automatically on pull requests and on pushes to `main`, and can be
triggered manually from the Actions tab (`workflow_dispatch`).
