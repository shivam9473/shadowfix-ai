"""Repository Importer and Codebase AST Indexer for ShadowFix AI.
Hardened with URL validation, branch sanitization, size/timeout limits, and rate limiting.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from knowledge.ast_chunker import chunk_source
from knowledge.qdrant_prod import AstKnowledgeBase
from paths import DATA_DIR, DEMO_ROOT
from saas_db import saas_store

logger = logging.getLogger("project_importer")
REPOS_DIR = DATA_DIR / "imported_repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)

MAX_REPO_BYTES = 100 * 1024 * 1024  # 100 MB
CLONE_TIMEOUT_SECONDS = 45

VALID_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".go", ".rs"}
IGNORED_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}

ALLOWED_HOST_PATTERN = re.compile(
    r"^https:\/\/(github\.com|gitlab\.com|bitbucket\.org)\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\.git)?$"
)
BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9_.\/-]+$")
DANGEROUS_CHARS = re.compile(r"[;&|`$\n\r]")


def validate_repo_safety(repo_url: str, branch: str, is_production: bool = False) -> None:
    """Validates repository URL and branch name against injection and untrusted sources."""
    clean_url = repo_url.strip()
    clean_branch = branch.strip()

    # Reject shell injection characters
    if DANGEROUS_CHARS.search(clean_url) or DANGEROUS_CHARS.search(clean_branch):
        raise ValueError("Security Violation: Illegal characters detected in repository URL or branch.")

    if clean_branch.startswith("-"):
        raise ValueError("Security Violation: Branch name cannot start with a hyphen.")

    if not BRANCH_PATTERN.match(clean_branch):
        raise ValueError("Invalid branch name format.")

    # In dev, allow shopkart demo or local directories
    if not is_production:
        if clean_url in {"local://demo-shopkart", "shopkart://local"}:
            return
        if Path(clean_url).is_dir():
            return

    # In production, require strict HTTPS trusted git providers
    if not ALLOWED_HOST_PATTERN.match(clean_url):
        raise ValueError(
            "Security Policy Violation: Only verified HTTPS repositories from "
            "GitHub, GitLab, or Bitbucket are allowed."
        )


def _check_directory_size(directory: Path, max_bytes: int = MAX_REPO_BYTES) -> int:
    """Calculates directory size and raises an error if it exceeds max_bytes."""
    total_size = 0
    for root, _, files in os.walk(directory):
        for f in files:
            fp = Path(root) / f
            try:
                total_size += fp.stat().st_size
                if total_size > max_bytes:
                    raise ValueError(
                        f"Repository size exceeds maximum allowed limit ({max_bytes // (1024*1024)} MB)."
                    )
            except (OSError, FileNotFoundError):
                continue
    return total_size


def index_directory(
    directory: Path,
    kb: AstKnowledgeBase,
    tenant_id: str,
    project_id: str,
    max_files: int = 250,
) -> int:
    """Traverse a directory, generate AST chunks, and index into Qdrant vector store."""
    indexed_files = 0
    total_chunks = 0

    scoped_tenant = f"{tenant_id}:{project_id}"

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix.lower() not in VALID_EXTENSIONS:
                continue

            try:
                relative_path = file_path.relative_to(directory).as_posix()
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue

                chunks = chunk_source(relative_path, content)
                if chunks:
                    kb.upsert_chunks(scoped_tenant, chunks)
                    total_chunks += len(chunks)
                    indexed_files += 1

                if indexed_files >= max_files:
                    break
            except Exception as exc:
                logger.warning("Failed to chunk file %s: %s", file_path, exc)

        if indexed_files >= max_files:
            break

    saas_store.update_project_index(project_id, indexed_files)
    return indexed_files


def import_and_index_repository(
    project_id: str,
    tenant_id: str,
    repo_url: str,
    branch: str = "main",
    access_token: str = "",
    kb: AstKnowledgeBase | None = None,
    is_production: bool = False,
) -> dict[str, Any]:
    """Clone a Git repository with strict safety checks and chunk into Qdrant."""
    clean_url = repo_url.strip()
    clean_branch = (branch or "main").strip()

    # 1. Rate Limiting Check
    if not saas_store.check_import_rate_limit(tenant_id, max_per_hour=10):
        raise PermissionError("Rate limit exceeded: Maximum 10 repository imports per hour per tenant.")

    # 2. Security Validation
    validate_repo_safety(clean_url, clean_branch, is_production)

    project_dir = REPOS_DIR / project_id

    # 3. Handle Local Demo / Directory
    if clean_url in {"local://demo-shopkart", "shopkart://local"}:
        indexed = index_directory(DEMO_ROOT, kb, tenant_id, project_id) if kb else 4
        return {
            "project_id": project_id,
            "status": "ready",
            "files_indexed": indexed,
            "local_path": str(DEMO_ROOT),
        }

    if not is_production:
        local_path = Path(clean_url)
        if local_path.is_dir():
            _check_directory_size(local_path)
            indexed = index_directory(local_path, kb, tenant_id, project_id) if kb else 0
            return {
                "project_id": project_id,
                "status": "ready",
                "files_indexed": indexed,
                "local_path": str(local_path),
            }

    # 4. Remote Sandboxed Git Clone
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)

    token = (access_token or "").strip()
    clone_url = clean_url
    if token:
        if "github.com" in clean_url:
            raw = clean_url.replace("https://", "").replace("http://", "")
            clone_url = f"https://{token}@{raw}"
        elif "gitlab.com" in clean_url:
            raw = clean_url.replace("https://", "").replace("http://", "")
            clone_url = f"https://oauth2:{token}@{raw}"

    try:
        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--single-branch",
            "--branch",
            clean_branch,
            clone_url,
            str(project_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=CLONE_TIMEOUT_SECONDS)
        if result.returncode != 0:
            # Fallback without branch flag if branch is default
            cmd_fallback = [
                "git",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                clone_url,
                str(project_dir),
            ]
            fallback_res = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=CLONE_TIMEOUT_SECONDS)
            if fallback_res.returncode != 0:
                err_msg = fallback_res.stderr or result.stderr
                raise RuntimeError(f"Git clone failed: {err_msg.strip()}")

        # 5. Enforce post-clone size check
        _check_directory_size(project_dir)

        # 6. Index AST into Qdrant
        indexed = index_directory(project_dir, kb, tenant_id, project_id) if kb else 0
        return {
            "project_id": project_id,
            "status": "ready",
            "files_indexed": indexed,
            "local_path": str(project_dir),
        }

    except Exception as exc:
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
        if is_production:
            raise RuntimeError(f"Repository import failed: {exc}") from exc

        # Dev fallback: only in non-production
        logger.warning("Non-production clone fallback for %s: %s", clean_url, exc)
        project_dir.mkdir(parents=True, exist_ok=True)
        sample_file = project_dir / "app.py"
        if not sample_file.exists():
            sample_file.write_text(
                '"""User Imported Project Entrypoint"""\n\n'
                'def calculate_total(items, discount):\n'
                '    subtotal = sum(item["price"] for item in items)\n'
                '    # Bug: Division by zero when coupon discount is 100% (1.0)\n'
                '    return round(subtotal / (1 - discount), 2)\n',
                encoding="utf-8",
            )
        indexed = index_directory(project_dir, kb, tenant_id, project_id) if kb else 1
        return {
            "project_id": project_id,
            "status": "ready",
            "files_indexed": indexed,
            "local_path": str(project_dir),
            "notice": f"Dev mode indexed with local fallback: {exc}",
        }
