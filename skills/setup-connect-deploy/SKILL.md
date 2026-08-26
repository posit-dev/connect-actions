---
name: setup-connect-deploy
description: >-
  Set up GitHub Actions workflows to deploy an app to Posit Connect with
  posit-dev/connect-actions. Use when a user wants to add, scaffold, or
  configure Connect deployment (production deploy, PR draft previews, and
  preview cleanup) in a repo's .github/workflows — including choosing
  trusted publishing (OIDC) vs. API-key auth, authorizing the repository as a
  trusted publisher on Connect, and wiring up secrets.
---

# Set up Posit Connect deployment with connect-actions

This skill walks a repository through adding the
[`posit-dev/connect-actions`](https://github.com/posit-dev/connect-actions)
GitHub Actions: a `deploy` workflow (production deploy on push, draft previews
on pull requests) and, optionally, a `cleanup-previews` workflow that removes
those previews when a PR closes.

Work through the steps **in order**. Ask the user the questions as you reach
them rather than assuming answers — the right workflow depends on how they
authenticate and whether they want PR previews. Do not write any files until
Step 6. (Step 3a can change configuration on the Connect server, but only after
the user opts in to it.)

---

## Step 1 — Check preconditions

These actions run *inside GitHub Actions*, so the repo must be a git repo with a
GitHub remote.

1. Confirm you're in a working tree:
   `git rev-parse --is-inside-work-tree`
2. Get the origin remote and confirm it points at GitHub; parse `<owner>/<repo>`
   from it:
   `git remote get-url origin`
   - If there is no remote, or it isn't a `github.com` URL, tell the user these
     actions only run on GitHub-hosted repos and stop unless they want to
     proceed anyway (e.g. they'll add the remote later).

Steps 3 and 3a use the GitHub CLI (`gh auth status`) and the `posit` CLI
(installed with `uv tool install git+https://github.com/posit-dev/posit-cli`).
Neither is required to scaffold the workflows — check for them when you get
there, and fall back to telling the user what to do in the UI if they're missing.

Then explain the one prerequisite the skill can't do for them:

> The `deploy` action **updates existing content** on Connect — it does not
> create a new content item. You must have deployed this app to Connect at least
> once already (via the Posit Publisher extension for Positron/VS Code, the
> `rsconnect` CLI, or the Connect UI). If you used Posit Publisher, it wrote
> `.posit/publish/deployments/*.toml` files — commit those; this skill will read
> them.

Ask the user to confirm the content already exists on Connect before continuing.

## Step 2 — Resolve the deploy target (server URL + content GUID)

The action finds the target the same way — follow the same 3-tier logic here so
what you scaffold matches what will run:

1. **Deployment file (preferred).** Look for `.posit/publish/deployments/*.toml`
   (search recursively).
   - **Exactly one** file: read it (it's TOML) and pull `server_url` and `id`
     (the content GUID); the `[configuration] entrypoint` is used by the action
     automatically. Show these to the user to confirm. The workflow can then
     omit `connect-server`/`content-guid` entirely — the action auto-detects the
     single file.
   - **More than one** file: the action can't auto-detect. Either ask which one
     to use (pass it via the `deployment-file` input) or, if these are separate
     apps, set up one deploy step per app with the `path:` input (see Step 5).
   - **None:** ask the user for the **Connect server URL** and the **content
     GUID**, which you'll pass as the `connect-server` and `content-guid`
     inputs. (The GUID is the UUID in the content's URL / Info panel on Connect.)
2. If the app lives in a subdirectory of the repo, note it — you'll pass it as
   the `path:` input in Step 5.

**Important — `path:` narrows auto-detection.** The action resolves the target
from the `path` directory (its config step runs with that as the working
directory), so auto-detection only searches `<path>/.posit/publish/deployments/`,
not the repo root. If you set `path:` to a subdirectory and the deployment TOML
is *not* under it, auto-detection won't find it: either point `deployment-file`
at a path reachable from `path`, or pass explicit `connect-server` +
`content-guid`. When `path` is the repo root (the default), the single-file
auto-detection above works as described.

## Step 3 — Choose authentication (the key decision)

Ask the user which auth method to use. Recommend Trusted Publishing when their
Connect server supports it.

**Option A — Trusted Publishing (OIDC), recommended.**
- Requires Connect **2026.07.0 or newer** with an **Enhanced or Advanced
  license**, and a trusted publisher configured for this content (on the
  content's **Source** tab in Connect, tied to this GitHub repo). On an older
  server or lesser license, login fails with a clear error---use Option B
  instead.
- No secret is stored in GitHub. The workflow job just needs
  `permissions: id-token: write` so it can request an OIDC token, which the
  action exchanges for a short-lived Connect key.
- Nothing goes in the workflow for auth beyond that permission.
- If the user picks this, **offer to authorize the repository on Connect for
  them** — see Step 3a. Skip Step 3a for Option B.

**Option B — API key in a repo secret.**
- The user needs a Connect API key with at least **publisher** privileges (from
  their Connect account settings).
- Store it as a repository secret — do **not** put a key in the workflow file.
  Offer to set it for them:
  `gh secret set CONNECT_API_KEY` (paste the key when prompted), or via the
  GitHub UI under Settings → Secrets and variables → Actions.
- The workflow references it as `connect-api-key: ${{ secrets.CONNECT_API_KEY }}`
  and does **not** need `id-token: write`.

## Step 3a — Authorize the repository on Connect (Trusted Publishing only)

Ask whether the trusted publisher is already configured for this content. If it
is, skip ahead. Otherwise offer to configure it now — you can do the whole thing
from the command line, but it needs the user's *own* Connect credentials (a
trusted-publishing credential cannot manage trusted publishers) and they must be
the content's owner or a collaborator who can change its settings.

**1. Determine the `repository` value.** This is the repository segment of the
`sub` (subject) claim in the OIDC tokens the repo issues, and it is *not* always
`owner/repo`. Repositories created on or after **July 15, 2026** use [immutable
subject claims](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/),
which embed GitHub's numeric owner and repo IDs (`my-org@123456/my-repo@789012`);
older repos can opt in, and renames or transfers after that date also switch the
format. Getting this wrong is the classic failure: the config looks right but the
token exchange fails with an HTTP 400.

Ask GitHub directly rather than guessing — this reports exactly what the repo
produces:

```bash
gh api "repos/$ORG/$REPO/actions/oidc/customization/sub"
# {"use_default":true,"use_immutable_subject":false,"sub_claim_prefix":"repo:my-org/my-repo"}
```

The `repository` value is `sub_claim_prefix` with the leading `repo:` stripped.
If `sub_claim_prefix` doesn't start with `repo:` (a repo with a customized
subject claim template), the `github-actions` publisher type can't match it —
tell the user they need a **Custom OpenID Connect** publisher instead, and stop
there rather than registering something that won't work.

That endpoint needs admin access to the repo. If it fails with 403/404, fall
back: get the immutable identifiers and the creation date, and use the immutable
form when the repo was created on or after 2026-07-15 (otherwise plain
`owner/repo`), telling the user which you chose and why.

```bash
gh api "repos/$ORG/$REPO" --jq '"\(.owner.login)@\(.owner.id)/\(.name)@\(.id)"'
gh repo view "$ORG/$REPO" --json createdAt -q .createdAt
```

**2. Log in to Connect** as the user, if they aren't already
(`posit connect list` shows saved servers). This is interactive, so have *them*
run it — in Claude Code they can prefix with `!`:

```bash
posit connect login <server-url>
```

**3. Add the publisher**, using the content GUID from Step 2:

```bash
posit connect api "v1/content/$GUID/trusted-publishers" \
  -H "Content-Type: application/json" --input - <<JSON
{
  "name": "GitHub Actions ($REPOSITORY)",
  "template": "github-actions",
  "config": {"repository": "$REPOSITORY", "audience": "connect"}
}
JSON
```

Confirm the exact JSON with the user before sending it. `posit connect api` uses
the default saved server, so add `-s <server-url>` if they have more than one
saved. A 200/201 returns the service principal; adding the same workload twice
reuses the existing identity rather than duplicating it. Useful follow-ups:

```bash
posit connect api "v1/content/$GUID/trusted-publishers"                      # list
posit connect api "v1/content/$GUID/trusted-publishers/$SP_GUID" -X DELETE   # revoke
```

If this fails, report the error rather than working around it: a 402 means the
server lacks the Enhanced/Advanced license, a 403 means the account can't change
this content's permissions, and a 404 on the path itself means the server is
older than 2026.07.0. In each of those cases, recommend switching to Option B
(API key) instead.

## Step 4 — Check requirements / dependency files

Connect needs to know your app's dependencies. Check the app directory:

- **`manifest.json` present** → the action deploys it directly; app type,
  entrypoint, and dependencies come from the manifest as-is. Nothing more to do.
  (This is the usual path for **R** content — generate it with
  `rsconnect::writeManifest()`.)
- **Python, no manifest** → the action needs a `requirements.txt`. It looks for
  a dependency source in this order: an existing `requirements.txt`, then
  `uv.lock` (exported with pinned versions), then `pyproject.toml` (resolved at
  deploy time). Check what's present:
  - If none of `requirements.txt`, `uv.lock`, or `pyproject.toml` exists, warn
    the user — the deploy will fail without one.
  - Recommend committing a lockfile (`uv.lock` via `uv lock`, or a pinned
    `requirements.txt` via `uv pip compile pyproject.toml -o requirements.txt`)
    for reproducible deploys, optionally kept fresh with Dependabot.
- **Node.js, no manifest** → nothing to check; dependencies come from the app's
  `package.json`/`package-lock.json`, and with no Python dependency source
  present the action has nothing to generate.

Don't generate these files yourself unless the user asks — just report what you
found and recommend.

## Step 5 — PR previews, cleanup, and advanced options

Ask: **enable draft previews on pull requests?** (Default: yes.)

- **Yes** → the deploy workflow triggers on both `push` (to the default branch)
  and `pull_request`. On a PR it deploys a draft bundle and comments the preview
  URL, so the job needs `pull-requests: write` and a `github-token` input. Also
  **offer to add the `cleanup-previews` workflow**, which deletes those draft
  bundles when the PR closes (recommended — otherwise draft bundles accumulate
  on Connect). Draft previews require Connect **2025.06.0 or newer**; on older
  servers the deploy fails with a clear error and the user should choose **No**
  (or set `draft: false`).
- **No** → emit a push-only workflow (no `pull_request` trigger, no
  `pull-requests: write`, no `github-token`, no cleanup workflow).

Only if relevant, mention the advanced patterns (don't over-engineer the default
setup — point at the README rather than reproducing it):

- **App in a subdirectory:** add `path: <dir>` to the deploy step.
- **Multiple apps in one repo:** one deploy step per app, each with its own
  `path:`.
- **Multiple Connect servers** (fan-out, or dev-vs-prod per environment): see
  the "Deploying to multiple Connect servers" section of the connect-actions
  README.

## Step 6 — Write the workflow file(s)

Assemble `.github/workflows/deploy.yml` from the answers using the base template
below, then adjust:

- **Auth = OIDC:** keep `id-token: write`; do **not** add a `connect-api-key`
  input.
- **Auth = API key:** remove `id-token: write` from `permissions`; add
  `connect-api-key: ${{ secrets.CONNECT_API_KEY }}` to the step's `with:`.
- **Previews off:** remove the `pull_request:` trigger, the
  `pull-requests: write` permission, and the `github-token` input.
- **Target from explicit inputs** (no single deployment file): add
  `connect-server:` and `content-guid:` to `with:`. If a single deployment file
  was found *and* `path:` is not set (or points at the directory containing
  `.posit/`), omit both — the action auto-detects it. If `path:` points
  elsewhere, don't rely on auto-detection: add `deployment-file:` (reachable
  from `path`) or the explicit `connect-server`/`content-guid` (see Step 2).
- **Subdirectory / multiple apps:** add `path:` input(s) as needed.
- Pin the actions to `@main` (matches the connect-actions README examples).

Confirm the assembled file with the user before writing it, then create it.

### Base `deploy.yml` (OIDC + PR previews)

```yaml
name: Deploy to Connect

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
      id-token: write        # remove for API-key auth
      pull-requests: write   # remove if PR previews are disabled
    steps:
      - uses: actions/checkout@v7

      - name: Deploy to Connect
        uses: posit-dev/connect-actions/deploy@main
        with:
          # For API-key auth, add:
          #   connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          # If no single .posit deployment file is auto-detected, add:
          #   connect-server: https://connect.example.com
          #   content-guid: <content-guid>
          # For an app in a subdirectory, add:
          #   path: <subdir>
          github-token: ${{ github.token }}   # remove if previews are disabled
```

> Replace `main` in the `on:` triggers with the repo's actual default branch if
> it differs.

### `cleanup-previews.yml` (only when PR previews are enabled)

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
      id-token: write        # remove for API-key auth
      pull-requests: write
    steps:
      - uses: actions/checkout@v7

      - name: Cleanup preview bundles
        uses: posit-dev/connect-actions/cleanup-previews@main
        with:
          # For API-key auth, add:
          #   connect-api-key: ${{ secrets.CONNECT_API_KEY }}
          github-token: ${{ github.token }}
```

## Step 7 — Wrap up and tell the user what's left

After writing the files, summarize what was created and the remaining manual
steps, which depend on the auth choice:

- **OIDC:** if Step 3a authorized the repository, say so and note the
  `repository` value that was registered (so a later repo rename is a known
  breaking change). If it was skipped, the remaining step is to enable Trusted
  Publishing for this content on Connect (Source tab), tied to this GitHub repo,
  using the subject-claim format from Step 3a.
- **API key:** confirm the `CONNECT_API_KEY` secret is set on the repo.

Then suggest committing the workflow(s) and opening a pull request to exercise
the preview flow (or pushing to the default branch to trigger a production
deploy). Point them at the connect-actions README for the full input/output
reference and multi-server patterns.
