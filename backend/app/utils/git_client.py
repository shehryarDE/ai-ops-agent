import os
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime


# ─────────────────────────────────────────────────────────────────
# GIT CLIENT
# Creates hotfix branches and opens PRs automatically
# Only runs when risk_level == "low" and auto_fix is enabled
# Requires: GITHUB_TOKEN and GITHUB_REPO in .env
# ─────────────────────────────────────────────────────────────────

class GitClient:

    def __init__(self, github_token: str, github_repo: str, base_branch: str = "main"):
        """
        github_token: personal access token with repo scope
        github_repo:  "owner/repo" format e.g. "sheheryar/ai-ops-agent"
        base_branch:  branch to branch off from (usually "main" or "dev")
        """
        self.token       = github_token
        self.repo        = github_repo
        self.base_branch = base_branch
        self.api_base    = "https://api.github.com"
        self.enabled     = bool(github_token and github_repo)

        if not self.enabled:
            print("ℹ️  Git client disabled — set GITHUB_TOKEN and GITHUB_REPO to enable auto-PR")


    # ── BRANCH ───────────────────────────────────────────────────

    def create_hotfix_branch(self, issue_summary: str) -> str:
        """
        Creates a new branch named: aiops/hotfix/<timestamp>-<slug>
        Returns the branch name.
        """
        if not self.enabled:
            return ""

        # build a clean branch name from the issue summary
        slug = (
            issue_summary.lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("_", "-")
        )
        # keep it short
        slug = "-".join(slug.split("-")[:6])
        slug = "".join(c for c in slug if c.isalnum() or c == "-")

        timestamp   = datetime.now().strftime("%Y%m%d-%H%M")
        branch_name = f"aiops/hotfix/{timestamp}-{slug}"

        try:
            # get the SHA of the base branch
            sha = self._get_branch_sha(self.base_branch)

            # create the new branch at that SHA
            self._github_post(
                f"/repos/{self.repo}/git/refs",
                {"ref": f"refs/heads/{branch_name}", "sha": sha}
            )

            print(f"✅ Created branch: {branch_name}")
            return branch_name

        except Exception as e:
            print(f"⚠️  Could not create branch: {e}")
            return ""


    # ── COMMIT ───────────────────────────────────────────────────

    def commit_fix(
        self,
        branch_name: str,
        file_path: str,
        original_content: str,
        fixed_content: str,
        commit_message: str
    ) -> bool:
        """
        Commits the fixed file content to the hotfix branch.
        Works by updating the file blob directly via GitHub API.
        """
        if not self.enabled or not branch_name:
            return False

        try:
            import base64

            # GitHub API needs base64-encoded content
            encoded = base64.b64encode(fixed_content.encode()).decode()

            # get current file SHA (needed to update existing file)
            file_sha = self._get_file_sha(file_path, branch_name)

            payload = {
                "message": f"[AI-OPS] {commit_message}",
                "content": encoded,
                "branch":  branch_name,
            }
            if file_sha:
                payload["sha"] = file_sha   # required for updates, not new files

            self._github_put(
                f"/repos/{self.repo}/contents/{file_path}",
                payload
            )

            print(f"✅ Committed fix to {branch_name}")
            return True

        except Exception as e:
            print(f"⚠️  Could not commit fix: {e}")
            return False


    # ── PULL REQUEST ─────────────────────────────────────────────

    def open_pr(
        self,
        branch_name: str,
        issue_summary: str,
        diagnosis: dict,
        proposed_fix: dict,
        test_passed: bool
    ) -> str:
        """
        Opens a PR from the hotfix branch into base_branch.
        PR body contains full diagnosis, fix description, and test result.
        Returns the PR URL or empty string on failure.
        """
        if not self.enabled or not branch_name:
            return ""

        title = f"[AI-OPS] {issue_summary[:72]}"
        body  = self._build_pr_body(diagnosis, proposed_fix, test_passed)

        try:
            response = self._github_post(
                f"/repos/{self.repo}/pulls",
                {
                    "title": title,
                    "body":  body,
                    "head":  branch_name,
                    "base":  self.base_branch,
                }
            )
            pr_url = response.get("html_url", "")
            print(f"✅ PR opened: {pr_url}")
            return pr_url

        except Exception as e:
            print(f"⚠️  Could not open PR: {e}")
            return ""


    # ── LOCAL GIT (fallback when no GitHub token) ────────────────

    def local_commit(
        self,
        file_path: str,
        fixed_content: str,
        issue_summary: str
    ) -> bool:
        """
        If no GitHub token is set, apply the fix locally and git commit.
        Engineer can then push and open PR manually.
        """
        try:
            # write the fixed content to disk
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            # git add + commit
            subprocess.run(["git", "add", file_path], check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"[AI-OPS] fix: {issue_summary[:60]}"],
                check=True, capture_output=True
            )

            print(f"✅ Local git commit applied for: {file_path}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"⚠️  Local git commit failed: {e.stderr.decode()}")
            return False
        except Exception as e:
            print(f"⚠️  Could not write fix to disk: {e}")
            return False


    # ── PR BODY BUILDER ──────────────────────────────────────────

    def _build_pr_body(
        self,
        diagnosis: dict,
        proposed_fix: dict,
        test_passed: bool
    ) -> str:
        test_badge = "✅ PASSED" if test_passed else "⚠️ NOT VERIFIED"

        return f"""## 🤖 AI-OPS Automated Hotfix

> This PR was opened automatically by the AI-Ops Agent after diagnosing
> a production issue and verifying the fix passed tests.

---

### Issue Found

| Field | Detail |
|---|---|
| **Type** | `{diagnosis.get('issue_type', 'unknown')}` |
| **Severity** | `{diagnosis.get('severity', 'unknown').upper()}` |
| **Summary** | {diagnosis.get('issue_summary', '')} |
| **Confidence** | {diagnosis.get('confidence_score', 0):.0%} |

**Root Cause:**
{diagnosis.get('root_cause', 'See code changes')}

**Production Impact:**
{diagnosis.get('production_impact', 'See diagnosis')}

---

### Fix Applied

{proposed_fix.get('fix_description', '')}

**Test command:** `{proposed_fix.get('test_command', 'N/A')}`
**Test result:** {test_badge}

**Rollback plan:**
{proposed_fix.get('rollback_plan', 'Revert this commit')}

---

### Code Change

```python
# BEFORE
{proposed_fix.get('code_before', '')}

# AFTER
{proposed_fix.get('code_after', '')}
```

---

*Auto-generated by AI-Ops Agent · Review before merging*
"""


    # ── GITHUB API HELPERS ───────────────────────────────────────

    def _github_request(self, method: str, endpoint: str, payload: dict = None) -> dict:
        url     = f"{self.api_base}{endpoint}"
        data    = json.dumps(payload).encode() if payload else None
        headers = {
            "Authorization": f"token {self.token}",
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
            "User-Agent":    "ai-ops-agent/1.0"
        }

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise Exception(f"GitHub API {e.code}: {body}")

    def _github_post(self, endpoint: str, payload: dict) -> dict:
        return self._github_request("POST", endpoint, payload)

    def _github_put(self, endpoint: str, payload: dict) -> dict:
        return self._github_request("PUT", endpoint, payload)

    def _github_get(self, endpoint: str) -> dict:
        return self._github_request("GET", endpoint)

    def _get_branch_sha(self, branch: str) -> str:
        data = self._github_get(f"/repos/{self.repo}/git/ref/heads/{branch}")
        return data["object"]["sha"]

    def _get_file_sha(self, file_path: str, branch: str) -> str:
        """Returns SHA of existing file, or empty string if file doesn't exist yet."""
        try:
            data = self._github_get(
                f"/repos/{self.repo}/contents/{file_path}?ref={branch}"
            )
            return data.get("sha", "")
        except Exception:
            return ""   # new file — no SHA needed


# ── CONVENIENCE FUNCTION ──────────────────────────────────────────

def apply_and_commit(
    proposed_fix: dict,
    diagnosis: dict,
    test_passed: bool,
    github_token: str = "",
    github_repo: str = "",
    base_branch: str = "main"
) -> str:
    """
    Full auto-commit flow:
      1. Create hotfix branch
      2. Commit the fix
      3. Open PR

    Returns PR URL (or empty string if git not configured).
    Falls back to local git commit if no GitHub token.
    """
    client = GitClient(github_token, github_repo, base_branch)

    issue_summary = diagnosis.get("issue_summary", "unknown-issue")
    files         = proposed_fix.get("files_to_change", [])
    code_after    = proposed_fix.get("code_after", "")

    if not files:
        print("⚠️  No files to change — skipping git commit")
        return ""

    # ── GitHub flow
    if client.enabled:
        branch = client.create_hotfix_branch(issue_summary)
        if branch:
            file_path = files[0]
            committed = client.commit_fix(
                branch_name      = branch,
                file_path        = file_path,
                original_content = proposed_fix.get("code_before", ""),
                fixed_content    = code_after,
                commit_message   = f"fix: {issue_summary[:60]}"
            )
            if committed:
                return client.open_pr(branch, issue_summary, diagnosis, proposed_fix, test_passed)

    # ── local git fallback
    else:
        client.local_commit(files[0], code_after, issue_summary)

    return ""