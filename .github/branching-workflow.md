# Branching and Release Workflow

## Branch model

- `develop`: main integration branch for all fixes and features.
- `v0`, `v1`: version-specific maintenance branches.

## Backport flow

1. Merge changes to `develop` first.
2. On the merged `develop` PR, run Mergify backport commands in comments:
   - `@Mergifyio backport v0`
   - `@Mergifyio backport v1`
3. Review and merge the backport PR(s) opened by Mergify.

## Release flow

- Scheduled release: every Tuesday at 09:00 UTC, GitHub Actions runs semantic-release for each release branch.
- Manual release: run the `Auto Release` workflow with:
  - `release_branch=all|v0|v1`
  - optional `dry_run=true`.

## Develop branch protection

Direct pushes to `develop` must be disabled from repository settings:

1. Open repository settings -> Branches -> Branch protection rules (or Rulesets).
2. Add a protection rule for `develop`.
3. Enable at least:
   - Require a pull request before merging.
   - Restrict who can push to matching branches.
   - Include administrators.

This repository config cannot enforce branch protection by itself; it must be set in GitHub repository settings.
