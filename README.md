# connect-actions

Deploy to [Posit Connect](https://posit.co/products/enterprise/connect/) from GitHub Actions. Includes support for deploying draft versions of content on pull requests, git metadata annotations, and trusted publishing without API keys using OIDC.

The purpose of these actions is to allow you to maintain content on Connect using your CI/CD workflow. Once you have deployed the initial version of your content, use these actions to link it to your GitHub repository. These will help you:

* Ensure that the deployed version of your content corresponds to the latest version of the code on your default branch
* Only deploy if tests pass
* Make sure that your app runs correctly on Connect, in a draft view, before deploying it for everyone

These actions supersede the [`rstudio/actions/connect-publish`](https://github.com/rstudio/actions/tree/main/connect-publish) action.

## Getting started

There are a few prerequisites to set up before you can use these actions:

1. Deploy your content to Connect for the first time by other means. The `deploy` action here will not create a new content item for you; it will only update an existing one with new code. If you use the Publisher extension for Positron, VS Code, or other Code OSS forks, check in the `.posit/` TOML files it creates---this action can use them.
2. Configure auth. If your Connect server is version 2026.07.0 or newer, we recommend using the Trusted Publishing feature, which allows you to publish from this GitHub repository automatically. You can enable this in the "Access" tab of the content settings. If you are not using Trusted Publishing, you will need to get an API key with at least "publisher" privileges from your Connect account and add it as a GitHub Actions secret.
3. Make sure your requirements files are checked in. For Python content, this can either be a `uv.lock` file or a `requirements.txt`, and if you have neither, one can be generated from a `pyproject.toml` file. (We recommend that you keep both `pyproject.toml` and one of those lockfiles and use [Dependabot](https://docs.github.com/en/code-security/dependabot) to update the lockfile on a schedule so that your content stays up to date and security vulnerabilities are resolved.) For R, use the `rsconnect::writeManifest()` function to generate a `manifest.json` file.  

Then, you can add these actions. There are examples below, and there is (TODO!) an Agent Skill you can use to help add these actions to your GitHub repository. 

## Actions

### `deploy` - Deploy to Posit Connect

The default behavior is that on `push` events, it deploys the content and makes it the active version for all viewers. On pull requests, it creates a draft preview and comments on the PR the preview URL for you to review on Connect. To delete those draft bundles when the PR closes, add a workflow with the `cleanup-previews` action described below.

Here are the full list of inputs and outputs; below we describe what exactly is required.

#### Inputs

| Input | Required | Description |
|---|---|---|
| `connect-api-key` | No | Connect API key. If omitted, the action obtains a short-lived key via OIDC trusted publishing (requires `id-token: write` and a trusted publisher configured on Connect). |
| `audience` | No | Audience to request for the OIDC token when `connect-api-key` is omitted. Must match the trusted publisher's audience on Connect. Defaults to `connect`. You generally don't want to change this. |
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

#### Configuration

The action requires two things at minimum: the destination to deploy to (Connect server URL and content GUID), and how to authenticate. 

To identify the destination, you can either provide `connect-server` and `content-guid` directly as arguments, or you can provide a path to the `deployment-file`, the TOML file written out by Posit Publisher. If you omit all three of these, the action will look in the `.posit/publish/deployments/` directory and if there is a single deployment file in there, it will use that. If there are zero deployment files or more than one, you will need to provide the URL and GUID as arguments to the action. 

For authentication, we recommend using Trusted Publishing if your Connect server supports it. You do not need to provide any secrets for this to work, once you have enabled it for your content on your Connect server, but you do need to add `id-token: write` to the `permissions` block of your workflow job. If Trusted Publishing is not an option, you can provide `connect-api-key`, which should point to `${{ secrets.CONNECT_API_KEY }}` or similar---do not enter an API key in your workflow file directly. 

#### Requirements files

If a `manifest.json` exists at the root of your repo, the action deploys it directly using `rsconnect deploy manifest`. In this mode the manifest's declared app type, entrypoint, and dependencies are used as-is.

For Python content, Connect installs your app's dependencies from a `requirements.txt`. When one isn't present, the action generates it, as well as `manifest.json`, looking for a dependency source in this order:

1. **`requirements.txt`** -- if it already exists, it is used as-is.
2. **`uv.lock`** -- exported with `uv export --no-hashes --no-emit-project --frozen`, pinning the exact versions from your lockfile (the lockfile is used as-is; it is never re-resolved at deploy time).
3. **`pyproject.toml`** -- resolved at deploy time with `uv pip compile`.

For reproducible deploys, we recommend checking a lockfile into your repo alongside `pyproject.toml`: either a `uv.lock` (run `uv lock`) or a pinned `requirements.txt` (run `uv pip compile pyproject.toml -o requirements.txt`). Without one, the action re-resolves your dependencies from `pyproject.toml` on every deploy, so an upstream release can change what gets deployed. To keep a checked-in lockfile fresh, add a scheduled job or a tool like [Dependabot](https://docs.github.com/en/code-security/dependabot) to open update PRs.

#### Example

Here's the simplest case, where you are using Trusted Publishing, have checked in the Publisher TOML deployment file, and have only one deployment file in your repository. The Connect server URL and content GUID are picked up from the deployment file, and there is no API key secret needed to publish. 

This workflow runs on the `main` branch and on all pull requests that point to `main`. On pull request, a draft deployment is made and a link is posted back to the PR, so that's why we need to pass in `github.token` so that the action can comment. 

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
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v7

      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@main
        with:
          github-token: ${{ github.token }}
```

With explicit server/GUID (no deployment file needed) and an API key in secrets:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v7

      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-server: https://connect.example.com
          connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          content-guid: 12345678-abcd-1234-abcd-1234567890ab
          github-token: ${{ github.token }}
```

#### Deploying to multiple Connect servers

There are two common ways to involve more than one Connect server, and they
solve different problems.

**Fan-out: the same content to several servers.** Deploy the same app to
multiple servers on every event--for example a primary and a mirror, or two
regional servers. Invoke the action once per server, giving each its own URL and
GUID:

```yaml
      - name: Deploy to server A
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-server: ${{ vars.CONNECT_A_URL }}
          content-guid: ${{ vars.CONTENT_A_GUID }}
          github-token: ${{ github.token }}

      - name: Deploy to server B
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-server: ${{ vars.CONNECT_B_URL }}
          content-guid: ${{ vars.CONTENT_B_GUID }}
          github-token: ${{ github.token }}
```

On a pull request, each invocation deploys its own draft and leaves its own
preview comment, keyed by the content it deploys. See
[`cleanup-previews`](#cleanup-previews---cleanup-pr-preview-bundles) for how
cleanup handles PRs with previews on more than one server.

**Per-environment: pull requests to dev, the default branch to production.** By
default, pull requests deploy a draft bundle to the *same* content that
production uses, so reviewers can preview the change without disturbing the live
version. An alternative is to keep two separate Connect servers--a **dev**
(staging) server and a **production** server--and deploy pull requests to dev as
fully activated content, deploying to production only when changes merge to your
default branch. Switch on `github.event_name` to choose the server, GUID, and (if
you use key auth) API key for each:

```yaml
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
    # Serialize deploys so two runs never race on the same content; a newer
    # commit cancels an in-flight older one.
    concurrency:
      group: connect-deploy-${{ github.event_name == 'pull_request' && 'dev' || 'prod' }}
      cancel-in-progress: true
    steps:
      - uses: actions/checkout@v6

      # Pull requests deploy to the dev server, activated (not a draft).
      - name: Deploy PR to dev Connect
        if: github.event_name == 'pull_request'
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-server: ${{ vars.DEV_CONNECT_URL }}
          content-guid: ${{ vars.DEV_CONTENT_GUID }}
          draft: false

      # Pushes to the default branch deploy to the production server.
      - name: Deploy to production Connect
        if: github.event_name == 'push'
        uses: posit-dev/connect-actions/deploy@main
        with:
          connect-server: ${{ vars.PROD_CONNECT_URL }}
          content-guid: ${{ vars.PROD_CONTENT_GUID }}
```

`draft: false` is what makes the PR deploy replace the active bundle on the dev
content instead of staging a draft alongside it. Because the deploy isn't a
draft, the action leaves no preview comment and creates no draft bundle to clean
up--so this workflow needs neither `pull-requests: write` permission nor the
[`cleanup-previews`](#cleanup-previews---cleanup-pr-preview-bundles) action.

> **Concurrent pull requests share one dev content.** Every open PR deploys to
> the same dev GUID, so the dev server always shows whichever PR deployed most
> recently--a later deploy overwrites an earlier one, and merging or closing a PR
> does not restore what was there before. This pattern suits a single shared
> staging environment, not per-PR isolation. If you need each PR previewed
> independently, use the default draft-preview workflow instead: each PR gets its
> own draft bundle on the same content, and `cleanup-previews` removes them when
> the PR closes. The `concurrency` block above only prevents two runs from racing
> at the same instant; it does not give each PR its own content.

#### Deploying multiple apps from one repository

This is separate from multi-server setups, but uses the same mechanism: if your
repo contains more than one app, invoke the action once per app and use the
`path` input to point each invocation at its subdirectory. It composes with
either multi-server pattern above.

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
      id-token: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v7

      - name: Cleanup preview bundles
        uses: posit-dev/connect-actions/cleanup-previews@main
        with:
          github-token: ${{ github.token }}
```

#### Previews on multiple servers

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
