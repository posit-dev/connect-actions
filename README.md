# connect-actions

Deploy to [Posit Connect](https://posit.co/products/enterprise/connect/) from GitHub Actions.

> Extremely beta! In active development! Please use and try this, and tell us how it goes--but be prepared.

## Actions

### `get-api-key` - Get Connect API Key via OIDC

Exchanges a GitHub OIDC token for a short-lived Posit Connect API key via [trusted publishing](https://docs.posit.co/connect/). This allows keyless authentication--no stored secrets required. Requires a content owner to have configured a *trusted publisher* for the target content on your Connect server, naming this GitHub repository.

`deploy` and `cleanup-previews` do this automatically when you don't pass `connect-api-key`, so you usually don't need this action directly. Use it when you want the API key as an output for other steps. Pass its output as the `connect-api-key` input of those actions.

Your workflow must grant `id-token: write` permission for the OIDC token request to succeed.

#### Inputs

| Input | Required | Description |
|---|---|---|
| `connect-server` | Yes | Connect server URL (e.g., `https://connect.example.com`) |
| `audience` | No | Audience to request for the OIDC token. Must match the audience configured on the trusted publisher in Connect. Defaults to `connect`. |

#### Outputs

| Output | Description |
|---|---|
| `api-key` | Connect API key obtained via OIDC token exchange |

#### Example

```yaml
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v6

      - name: Get Connect API key
        id: connect-auth
        uses: posit-dev/connect-actions/get-api-key@main
        with:
          connect-server: ${{ vars.CONNECT_URL }}

      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-api-key: ${{ steps.connect-auth.outputs.api-key }}
          github-token: ${{ github.token }}
```

> Your workflow must include `id-token: write` in its permissions for the OIDC token request to succeed.

---

### `deploy` - Deploy to Posit Connect

Deploys a new version of your content to Connect. On push to the default branch, deploys to production. On pull requests, creates a draft preview bundle and comments the preview URL. To clean up those drafts when the PR closes, add a workflow with the `cleanup-previews` described below.

The content must already exist on Connect. The purpose of this action is to allow you to update it via GitHub Actions so that it is integrated into your CI/CD workflow.

> Currently, only content types supported by the [`rsconnect` CLI](https://github.com/posit-dev/rsconnect-python/) are supported in this action--basically, Python apps. 

#### Inputs

| Input | Required | Description |
|---|---|---|
| `connect-api-key` | No | Connect API key. If omitted, the action obtains a short-lived key via OIDC trusted publishing (requires `id-token: write` and a trusted publisher configured on Connect). |
| `audience` | No | Audience to request for the OIDC token when `connect-api-key` is omitted. Must match the trusted publisher's audience on Connect. Defaults to `connect`. |
| `connect-server` | No | Connect server URL. Can be read from `deployment-file` instead. |
| `content-guid` | No | Content GUID. Can be read from `deployment-file` instead. |
| `deployment-file` | No | Path to `.posit` deployment TOML file. Auto-detects from `.posit/publish/deployments/` if omitted and `connect-server`/`content-guid` are not set. |
| `path` | No | Path to the application directory within the repository. Defaults to the repository root. Use this when your app lives in a subdirectory of your repo. |
| `draft` | No | Deploy as a draft (preview) bundle instead of activating it. Defaults to `true` on `pull_request` events and `false` otherwise. Set it explicitly to override--e.g. `false` to publish directly from a PR, or `true` to stage a draft from a push. |
| `github-token` | No | GitHub token for commenting preview URLs on PRs |
| `rsconnect-args` | No | Additional arguments passed to `rsconnect deploy` |

#### Outputs

| Output | Description |
|---|---|
| `content-url` | URL of the deployed content |

#### Configuration resolution

The action resolves the Connect server URL, content GUID, and entrypoint through this priority order:

1. **Explicit inputs** - `connect-server` and `content-guid` provided directly
2. **Deployment file** - parsed from the TOML file specified by `deployment-file`
3. **Auto-detection** - scans `.posit/publish/deployments/` for a single `.toml` file (errors if zero or multiple are found)

Basically, if you deploy your content from Posit Publisher (in VS Code, Positron, or other Code OSS fork), commit the TOML files it generates to the repo, and assuming you only have one deployment target, the action will pick up everything it needs from it.

#### Requirements generation

Connect installs your app's dependencies from a `requirements.txt`. When one isn't present, the action generates it, looking for a dependency source in this order:

1. **`requirements.txt`** -- if it already exists, it is used as-is.
2. **`uv.lock`** -- exported with `uv export --no-hashes --no-emit-project --frozen`, pinning the exact versions from your lockfile (the lockfile is used as-is; it is never re-resolved at deploy time).
3. **`pyproject.toml`** -- resolved at deploy time with `uv pip compile`.

For reproducible deploys, we recommend checking a lockfile into your repo alongside `pyproject.toml`: either a `uv.lock` (run `uv lock`) or a pinned `requirements.txt` (run `uv pip compile pyproject.toml -o requirements.txt`). Without one, the action re-resolves your dependencies from `pyproject.toml` on every deploy, so an upstream release can change what gets deployed. To keep a checked-in lockfile fresh, add a scheduled job or a tool like [Dependabot](https://docs.github.com/en/code-security/dependabot) to open update PRs.

#### Deploying with a `manifest.json`

If a `manifest.json` exists at the root of your repo, the action deploys it directly using `rsconnect deploy manifest`. In this mode the manifest's declared app type, entrypoint, and dependencies are used as-is, so `requirements.txt` is not generated and the app type is not looked up from Connect.

#### Example

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v6

      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          github-token: ${{ github.token }}
```

With explicit server/GUID (no deployment file needed):

```yaml
      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-server: https://connect.example.com
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          content-guid: 12345678-abcd-1234-abcd-1234567890ab
          github-token: ${{ github.token }}
```

If you want to deploy something to multiple Connect servers, or you have multiple apps in your git repository, you can use the `posit-dev/connect-actions/deploy` multiple times. Use the `path` input to point each invocation at the appropriate subdirectory:

```yaml
      - name: Deploy app1
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          github-token: ${{ github.token }}
          path: apps/app1

      - name: Deploy app2
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          github-token: ${{ github.token }}
          path: apps/app2
```

On a pull request, each invocation leaves its own preview comment, keyed by the
content it deploys. See [`cleanup-previews`](#cleanup-previews---cleanup-pr-preview-bundles)
for how cleanup handles PRs with previews on more than one server.

---

### `cleanup-previews` - Cleanup PR Preview Bundles

Deletes draft bundles that were deployed to Connect as PR previews. Designed to run when a PR is closed (merged or abandoned). Finds bundle IDs from PR comments left by the `deploy` action and deletes them via the Connect API.

The example below also includes a `workflow_dispatch` trigger, which can be used to do manual cleanup, whether because the action failed previously (sorry!) or if preview bundle links showed up after the original cleanup ran. 

#### Inputs

| Input | Required | Description |
|---|---|---|
| `connect-api-key` | No | Connect API key. If omitted, the action obtains a short-lived key via OIDC trusted publishing (requires `id-token: write` and a trusted publisher configured on Connect). An API key is tied to a single server, so pair it with `connect-server` when a PR targets more than one. |
| `audience` | No | Audience to request for the OIDC token when `connect-api-key` is omitted. Must match the trusted publisher's audience on Connect. Defaults to `connect`. |
| `connect-server` | No | Connect server URL. Only needed to disambiguate when a PR has previews on more than one server (run one cleanup step per server). Otherwise it is inferred from the preview comment. |
| `github-token` | Yes | GitHub token for reading/commenting on PRs |

The server, content GUID, and bundle IDs to delete are read from the preview
comments the `deploy` action leaves on the PR, so cleanup needs no deployment
file or content GUID of its own.

#### Example

```yaml
name: Cleanup PR Previews

on:
  pull_request:
    types: [closed]
  workflow_dispatch:
    inputs:
      pr_number:
        description: Pull request number to clean up
        required: true
        type: number

jobs:
  cleanup:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v6

      - name: Cleanup preview bundles
        uses: posit-dev/connect-actions/cleanup-previews@main
        with:
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          github-token: ${{ github.token }}
```

#### Previews on multiple servers

When a PR has previews on a single server (the common case), one cleanup step
suffices and you don't need to pass `connect-server` -- it's inferred from the
preview comment. With OIDC, that means cleanup runs with no Connect arguments at
all.

If a PR has previews on more than one server, run one cleanup step per server.
A Connect API key is scoped to one server, so pair each key with its
`connect-server`:

```yaml
      - name: Cleanup previews on server A
        uses: posit-dev/connect-actions/cleanup-previews@main
        with:
          connect-server: https://connect-a.example.com
          connect-api-key: ${{ secrets.CONNECT_A_API_KEY }}
          github-token: ${{ github.token }}

      - name: Cleanup previews on server B
        uses: posit-dev/connect-actions/cleanup-previews@main
        with:
          connect-server: https://connect-b.example.com
          connect-api-key: ${{ secrets.CONNECT_B_API_KEY }}
          github-token: ${{ github.token }}
```

With OIDC you still need one step per server (each exchanges a token for that
server), but you only pass `connect-server`, not a key.

---

## Full lifecycle example

Using both actions together gives you a complete PR preview workflow:

1. **PR opened/updated** -- `deploy` creates a draft bundle and comments the preview URL
2. **PR closed/merged** -- `cleanup-previews` deletes the draft bundles

### With OIDC (recommended)

If a content owner has configured a [trusted publisher](https://docs.posit.co/connect/) for your content on Connect, you can use keyless authentication instead of storing API key secrets. Just grant `id-token: write` permission and omit `connect-api-key`--the actions exchange a GitHub OIDC token for a short-lived key automatically.

Trusted publishing requires Connect 2026.07.0 or newer.

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v7

      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-server: ${{ vars.CONNECT_URL }}
          github-token: ${{ github.token }}
```

```yaml
# .github/workflows/cleanup-previews.yml
name: Cleanup PR Previews

on:
  pull_request:
    types: [closed]
  workflow_dispatch:
    inputs:
      pr_number:
        description: Pull request number to clean up
        required: true
        type: number

jobs:
  cleanup:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v7

      - name: Cleanup preview bundles
        uses: posit-dev/connect-actions/cleanup-previews@main
        with:
          github-token: ${{ github.token }}
```

> Cleanup reads the server from the preview comment, so no `connect-server` is
> needed here. Pass it only when a PR has previews on more than one server (see
> [Previews on multiple servers](#previews-on-multiple-servers)).

### With API key secret

If OIDC is not available, you can use a stored API key secret:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@v1
        with:
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          github-token: ${{ github.token }}
```

```yaml
# .github/workflows/cleanup-previews.yml
name: Cleanup PR Previews

on:
  pull_request:
    types: [closed]
  workflow_dispatch:
    inputs:
      pr_number:
        description: Pull request number to clean up
        required: true
        type: number

jobs:
  cleanup:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Cleanup preview bundles
        uses: posit-dev/connect-actions/cleanup-previews@v1
        with:
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          github-token: ${{ github.token }}
```

MIT
