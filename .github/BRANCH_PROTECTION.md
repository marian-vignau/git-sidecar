# Branch Protection Setup Guide

This repository requires branch protection rules for the `main` branch. Follow these steps to configure it:

## Via GitHub Web Interface

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Branches**
3. Click **Add rule** or edit existing rule for `main`
4. Configure the following settings:

   ### Branch protection rule for `main`:
   
   - ✅ **Protect matching branches**
   - ✅ **Require a pull request before merging**
     - ✅ Require approvals: **1** (adjust as needed)
     - ✅ Dismiss stale pull request approvals when new commits are pushed
   - ✅ **Require status checks to pass before merging**
     - ✅ Require branches to be up to date before merging
     - Select the following required checks (these will appear after the first PR):
       - `test (3.8)`
       - `test (3.9)`
       - `test (3.10)`
       - `test (3.11)`
       - `test (3.12)`
       - `lint`
     - **Note**: Check names may vary slightly. After creating your first PR, check the exact check names in the PR status checks section, then configure branch protection accordingly.
   - ✅ **Require conversation resolution before merging**
   - ✅ **Do not allow bypassing the above settings** (includes administrators)

## Via GitHub CLI

If you have GitHub CLI installed:

```bash
# Note: Adjust check names based on actual names shown in PR status checks
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test (3.8)","test (3.9)","test (3.10)","test (3.11)","test (3.12)","lint"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null
```

Replace `:owner/:repo` with your repository owner and name (e.g., `username/GitSidecar`).

## Via GitHub API

You can also use the GitHub REST API directly. See the [GitHub API documentation](https://docs.github.com/en/rest/branches/branch-protection) for details.

## Verification

After setting up branch protection:

1. Try to push directly to `main` - it should be blocked
2. Create a test PR - verify that CI checks run
3. Confirm that the PR cannot be merged until all checks pass
