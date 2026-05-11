# connect-actions

Deploy to [Posit Connect](https://posit.co/products/enterprise/connect/) from GitHub Actions.

> Extremely beta! In active development! Please use and try this, and tell us how it goes--but be prepared.

## Actions

### `deploy` - Deploy to Posit Connect

Deploys a new version of your content to Connect. On push to the default branch, deploys to production. On pull requests, creates a draft preview bundle and comments the preview URL. To clean up those drafts when the PR closes, add a workflow with the `cleanup-previews` described below.

The content must already exist on Connect. The purpose of this action is to allow you to update it via GitHub Actions so that it is integrated into your CI/CD workflow.

> Currently, only content types supported by the [`rsconnect` CLI](https://github.com/posit-dev/rsconnect-python/) are supported in this action--basically, Python apps. 

#### Inputs

| Input | Required | Description |
|---|---|---|
| `connect-api-key` | Yes | Connect API key |
| `connect-server` | No | Connect server URL. Can be read from `deployment-file` instead. |
| `content-guid` | No | Content GUID. Can be read from `deployment-file` instead. |
| `deployment-file` | No | Path to `.posit` deployment TOML file. Auto-detects from `.posit/publish/deployments/` if omitted and `connect-server`/`content-guid` are not set. |
| `path` | No | Path to the application directory within the repository. Defaults to the repository root. Use this when your app lives in a subdirectory of your repo. |
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

If no `requirements.txt` exists in your repo, the action generates one from `pyproject.toml` using `uv pip compile`. If you already have a `requirements.txt`, it is used as-is.

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

---

### `cleanup-previews` - Cleanup PR Preview Bundles

Deletes draft bundles that were deployed to Connect as PR previews. Designed to run when a PR is closed (merged or abandoned). Finds bundle IDs from PR comments left by the `deploy` action and deletes them via the Connect API.

The example below also includes a `workflow_dispatch` trigger, which can be used to do manual cleanup, whether because the action failed previously (sorry!) or if preview bundle links showed up after the original cleanup ran. 

#### Inputs

| Input | Required | Description |
|---|---|---|
| `connect-api-key` | Yes | Connect API key |
| `connect-server` | No | Connect server URL. Can be read from `deployment-file` instead. |
| `content-guid` | No | Content GUID. Can be read from `deployment-file` instead. |
| `deployment-file` | No | Path to `.posit` deployment TOML file. Auto-detects if omitted. |
| `path` | No | Path to the application directory within the repository. Defaults to the repository root. Should match the `path` used in the `deploy` action. |
| `github-token` | Yes | GitHub token for reading/commenting on PRs |

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

---

## Full lifecycle example

Using both actions together gives you a complete PR preview workflow:

1. **PR opened/updated** -- `deploy` creates a draft bundle and comments the preview URL
2. **PR closed/merged** -- `cleanup-previews` deletes the draft bundles

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
