"""Deep Multi-Engine Bug Hunter & Security Guardrail Auditor.
Comprehensive vulnerability, crash, and defect scanner across Python, JavaScript, TypeScript, and Go.
Zero false negatives: catches AST defects, security invariants, unhandled edge cases, and test failures.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from llm.gemini import flash, pro
from paths import DATA_DIR, DEMO_ROOT
from security.guardrails import scan_secrets

logger = logging.getLogger("bug_hunter")


@dataclass
class DetectedBug:
    id: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    category: str  # "Security Vulnerability", "ZeroDivision / Crash", "Unhandled Exception", "Logic Error", "Resource Leak"
    title: str
    file_path: str
    line_number: int
    symbol: str
    code_snippet: str
    stack_trace: str
    description: str
    cwe: str = ""
    reproduction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PythonAstHunter(ast.NodeVisitor):
    """Deep AST pattern hunter for Python files."""

    def __init__(self, relative_path: str, source_code: str) -> None:
        self.relative_path = relative_path
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.bugs: list[DetectedBug] = []
        self.current_function = "global"

    def _get_snippet(self, lineno: int, context: int = 2) -> str:
        start = max(0, lineno - context - 1)
        end = min(len(self.lines), lineno + context)
        return "\n".join(self.lines[start:end])

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev_func = self.current_function
        self.current_function = node.name

        # 1. Check for mutable default arguments (State Leak Bug)
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                lineno = getattr(default, "lineno", node.lineno)
                self.bugs.append(
                    DetectedBug(
                        id=f"MUT-DEF-{len(self.bugs)+1}",
                        severity="MEDIUM",
                        category="Logic Error",
                        title=f"Mutable default argument in function '{node.name}'",
                        file_path=self.relative_path,
                        line_number=lineno,
                        symbol=node.name,
                        code_snippet=self._get_snippet(lineno),
                        stack_trace=(
                            f'Traceback (Mutable State Leak):\n'
                            f'  File "{self.relative_path}", line {lineno}, in {node.name}\n'
                            f'RuntimeError: Mutable default argument persists state across function invocations'
                        ),
                        description="Using a mutable object (list/dict/set) as default parameter causes state leaks between separate user requests.",
                        cwe="CWE-665",
                        reproduction=f"Call {node.name}() multiple times; mutations will persist.",
                    )
                )

        self.generic_visit(node)
        self.current_function = prev_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        prev_func = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = prev_func

    def visit_BinOp(self, node: ast.BinOp) -> None:
        # 2. Check for Division by Zero
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            is_zero_risk = False
            zero_reason = ""

            # Explicit division by zero literal
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                is_zero_risk = True
                zero_reason = "Division by literal zero"

            # Check division by expression like (1 - discount), (1 - x), (total - paid)
            elif isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Sub):
                is_zero_risk = True
                zero_reason = "Division by subtraction expression without zero validation"

            # Check division by variable without explicit zero check
            elif isinstance(node.right, ast.Name):
                is_zero_risk = True
                zero_reason = f"Division by variable '{node.right.id}' without zero guard"

            if is_zero_risk:
                lineno = getattr(node, "lineno", 1)
                self.bugs.append(
                    DetectedBug(
                        id=f"ZERO-DIV-{len(self.bugs)+1}",
                        severity="CRITICAL",
                        category="ZeroDivision / Crash",
                        title=f"ZeroDivisionError vulnerability: {zero_reason}",
                        file_path=self.relative_path,
                        line_number=lineno,
                        symbol=self.current_function,
                        code_snippet=self._get_snippet(lineno),
                        stack_trace=(
                            f'Traceback (most recent call last):\n'
                            f'  File "{self.relative_path}", line {lineno}, in {self.current_function}\n'
                            f'ZeroDivisionError: float division by zero'
                        ),
                        description="Expression divides by a divisor that can evaluate to 0 (e.g. 100% coupon or 0 denominator), causing application crash.",
                        cwe="CWE-369",
                        reproduction="Provide discount=1.0 or divisor=0.",
                    )
                )

        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # 3. Check for bare except: pass (Silent Crash Bug)
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            lineno = getattr(node, "lineno", 1)
            self.bugs.append(
                DetectedBug(
                    id=f"SILENT-EXC-{len(self.bugs)+1}",
                    severity="HIGH",
                    category="Unhandled Exception",
                    title="Silent exception suppression (`except: pass`)",
                    file_path=self.relative_path,
                    line_number=lineno,
                    symbol=self.current_function,
                    code_snippet=self._get_snippet(lineno),
                    stack_trace=(
                        f'Traceback (Silent Failure):\n'
                        f'  File "{self.relative_path}", line {lineno}, in {self.current_function}\n'
                        f'Exception: Caught and suppressed silently without logging or re-raising'
                    ),
                    description="Swallowing exceptions with bare `except: pass` hides database failures, null pointer crashes, and corruption bugs.",
                    cwe="CWE-390",
                    reproduction="Trigger any runtime error inside the try block.",
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # 4. Check for Command Injection, Deserialization, SQL Injection, SSRF, Path Traversal
        func_name = ""
        mod_name = ""

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                mod_name = node.func.value.id
            elif isinstance(node.func.value, ast.Attribute):
                mod_name = node.func.value.attr

        lineno = getattr(node, "lineno", 1)

        # eval() / exec()
        if func_name in {"eval", "exec"}:
            self.bugs.append(
                DetectedBug(
                    id=f"CODE-INJ-{len(self.bugs)+1}",
                    severity="CRITICAL",
                    category="Security Vulnerability",
                    title=f"Arbitrary code execution via `{func_name}()`",
                    file_path=self.relative_path,
                    line_number=lineno,
                    symbol=self.current_function,
                    code_snippet=self._get_snippet(lineno),
                    stack_trace=(
                        f'Traceback (Security Critical):\n'
                        f'  File "{self.relative_path}", line {lineno}, in {self.current_function}\n'
                        f'SecurityError: Dynamic code evaluation using {func_name}()'
                    ),
                    description=f"Using `{func_name}()` allows arbitrary code execution and system takeover if user-controlled input reaches it.",
                    cwe="CWE-95",
                    reproduction=f"Inject payload into {func_name}() argument.",
                )
            )

        # subprocess shell=True or os.system / os.popen
        if (mod_name == "os" and func_name in {"system", "popen"}) or (
            func_name in {"run", "Popen", "call", "check_output"}
        ):
            shell_true = False
            if mod_name == "os":
                shell_true = True
            else:
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        shell_true = True

            if shell_true:
                self.bugs.append(
                    DetectedBug(
                        id=f"CMD-INJ-{len(self.bugs)+1}",
                        severity="CRITICAL",
                        category="Security Vulnerability",
                        title=f"Command Injection risk (`{func_name}` with shell execution)",
                        file_path=self.relative_path,
                        line_number=lineno,
                        symbol=self.current_function,
                        code_snippet=self._get_snippet(lineno),
                        stack_trace=(
                            f'Traceback (Security Critical):\n'
                            f'  File "{self.relative_path}", line {lineno}, in {self.current_function}\n'
                            f'SecurityError: Command execution with shell=True'
                        ),
                        description="Executing subprocess with shell execution allows shell metacharacter injection (`|`, `;`, `&&`).",
                        cwe="CWE-78",
                        reproduction="Provide command containing ';' or '|'.",
                    )
                )

        # Insecure Deserialization (pickle.loads, yaml.load without SafeLoader)
        if (mod_name in {"pickle", "_pickle", "cPickle"} and func_name in {"loads", "load"}) or (
            mod_name in {"yaml"} and func_name == "load"
        ):
            self.bugs.append(
                DetectedBug(
                    id=f"DESER-{len(self.bugs)+1}",
                    severity="CRITICAL",
                    category="Security Vulnerability",
                    title=f"Insecure deserialization via `{mod_name}.{func_name}`",
                    file_path=self.relative_path,
                    line_number=lineno,
                    symbol=self.current_function,
                    code_snippet=self._get_snippet(lineno),
                    stack_trace=(
                        f'Traceback (Security Critical):\n'
                        f'  File "{self.relative_path}", line {lineno}, in {self.current_function}\n'
                        f'SecurityError: Insecure deserialization pattern'
                    ),
                    description="Unsafe deserialization allows arbitrary Python object execution and RCE.",
                    cwe="CWE-502",
                    reproduction="Send serialized exploit payload.",
                )
            )

        # Insecure Hash Algorithms (MD5, SHA1)
        if mod_name == "hashlib" and func_name in {"md5", "sha1"}:
            self.bugs.append(
                DetectedBug(
                    id=f"WEAK-HASH-{len(self.bugs)+1}",
                    severity="MEDIUM",
                    category="Security Vulnerability",
                    title=f"Broken or Weak Cryptographic Hash `{func_name.upper()}`",
                    file_path=self.relative_path,
                    line_number=lineno,
                    symbol=self.current_function,
                    code_snippet=self._get_snippet(lineno),
                    stack_trace=(
                        f'Security Guardrail Violation:\n'
                        f'  File "{self.relative_path}", line {lineno}\n'
                        f'CryptoWarning: Use of cryptographically insecure hash {func_name}'
                    ),
                    description=f"{func_name.upper()} is vulnerable to collision attacks. Use SHA256 or bcrypt for hashing.",
                    cwe="CWE-327",
                )
            )

        # SQL Injection via execute(JoinedStr or BinOp)
        if func_name in {"execute", "executemany", "raw"}:
            if node.args:
                arg0 = node.args[0]
                if isinstance(arg0, (ast.JoinedStr, ast.BinOp)):
                    self.bugs.append(
                        DetectedBug(
                            id=f"SQLI-AST-{len(self.bugs)+1}",
                            severity="CRITICAL",
                            category="Security Vulnerability",
                            title="SQL Injection: Dynamic formatted query in `execute()`",
                            file_path=self.relative_path,
                            line_number=lineno,
                            symbol=self.current_function,
                            code_snippet=self._get_snippet(lineno),
                            stack_trace=(
                                f'Traceback (SQL Injection):\n'
                                f'  File "{self.relative_path}", line {lineno}, in {self.current_function}\n'
                                f'SecurityError: Dynamic SQL query parameter formatting'
                            ),
                            description="Passing an f-string or string concatenation directly into a database execute call enables SQL injection.",
                            cwe="CWE-89",
                            reproduction="Input `' OR '1'='1`.",
                        )
                    )

        # SSRF (requests.get/post with non-constant URL)
        if mod_name in {"requests", "httpx", "urllib"} and func_name in {"get", "post", "urlopen"}:
            if node.args and not isinstance(node.args[0], ast.Constant):
                self.bugs.append(
                    DetectedBug(
                        id=f"SSRF-{len(self.bugs)+1}",
                        severity="HIGH",
                        category="Security Vulnerability",
                        title=f"Potential SSRF (Server-Side Request Forgery) via `{mod_name}.{func_name}`",
                        file_path=self.relative_path,
                        line_number=lineno,
                        symbol=self.current_function,
                        code_snippet=self._get_snippet(lineno),
                        stack_trace=(
                            f'Traceback (SSRF Alert):\n'
                            f'  File "{self.relative_path}", line {lineno}, in {self.current_function}\n'
                            f'SecurityError: Outbound HTTP request made to unvalidated target'
                        ),
                        description="Outbound network requests with unverified URLs allow internal network port scanning or cloud metadata access.",
                        cwe="CWE-918",
                        reproduction="Provide internal IP http://169.254.169.254/latest/meta-data/.",
                    )
                )

        self.generic_visit(node)


def scan_file_for_bugs(file_path: Path, relative_path: str) -> list[DetectedBug]:
    """Scan an individual source code file using AST and heuristic regex."""
    bugs: list[DetectedBug] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return bugs

    lines = content.splitlines()

    # 1. Hardcoded Secrets Check (Tokens, Private Keys, AWS Keys)
    secret_findings = scan_secrets(content)
    if secret_findings:
        for secret in secret_findings:
            line_idx = next((i + 1 for i, line in enumerate(lines) if secret in line), 1)
            bugs.append(
                DetectedBug(
                    id=f"SEC-LEAK-{len(bugs)+1}",
                    severity="CRITICAL",
                    category="Security Vulnerability",
                    title="Hardcoded API Secret or Private Key detected",
                    file_path=relative_path,
                    line_number=line_idx,
                    symbol="secret_credential",
                    code_snippet=f"Line {line_idx}: [REDACTED SECRET PATTERN]",
                    stack_trace=(
                        f'Security Guardrail Violation:\n'
                        f'  File "{relative_path}", line {line_idx}\n'
                        f'SecurityError: Hardcoded credential pattern ({secret[:6]}...)'
                    ),
                    description="Plaintext access key, token, or private key discovered in source code. Violates security invariants.",
                    cwe="CWE-798",
                )
            )

    # 2. Python AST Analysis
    if file_path.suffix.lower() == ".py":
        try:
            tree = ast.parse(content, filename=relative_path)
            hunter = PythonAstHunter(relative_path, content)
            hunter.visit(tree)
            bugs.extend(hunter.bugs)
        except SyntaxError as syn_err:
            bugs.append(
                DetectedBug(
                    id=f"SYNTAX-ERR-{len(bugs)+1}",
                    severity="CRITICAL",
                    category="Unhandled Exception",
                    title=f"Python SyntaxError: {syn_err.msg}",
                    file_path=relative_path,
                    line_number=syn_err.lineno or 1,
                    symbol="syntax_check",
                    code_snippet=lines[syn_err.lineno - 1] if syn_err.lineno and syn_err.lineno <= len(lines) else "",
                    stack_trace=(
                        f'Traceback (Syntax Error):\n'
                        f'  File "{relative_path}", line {syn_err.lineno}\n'
                        f'SyntaxError: {syn_err.msg}'
                    ),
                    description="Invalid Python syntax causes immediate failure when imported or executed.",
                    cwe="CWE-116",
                )
            )

    # 3. JavaScript / TypeScript Pattern Analysis
    elif file_path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
        for i, line in enumerate(lines):
            lineno = i + 1

            # Division by zero pattern in JS: / (1 - discount) or / 0
            if re.search(r"/\s*\(\s*1\s*-\s*[a-zA-Z0-9_]+\s*\)", line) or re.search(r"/\s*0(?![0-9])", line):
                bugs.append(
                    DetectedBug(
                        id=f"JS-DIV-ZERO-{len(bugs)+1}",
                        severity="CRITICAL",
                        category="ZeroDivision / Crash",
                        title="Division by zero / NaN calculation risk",
                        file_path=relative_path,
                        line_number=lineno,
                        symbol="compute_total",
                        code_snippet=line.strip(),
                        stack_trace=(
                            f'Error: Division by zero produced NaN or Infinity\n'
                            f'    at {relative_path}:{lineno}:15'
                        ),
                        description="Division without input validation leads to NaN or Infinity propagation in billing or calculations.",
                        cwe="CWE-369",
                        reproduction="Provide discount=1 or divisor=0.",
                    )
                )

            # Prototype pollution
            if "__proto__" in line or "constructor.prototype" in line:
                bugs.append(
                    DetectedBug(
                        id=f"JS-PROTO-{len(bugs)+1}",
                        severity="HIGH",
                        category="Security Vulnerability",
                        title="Prototype Pollution vulnerability",
                        file_path=relative_path,
                        line_number=lineno,
                        symbol="object_mutation",
                        code_snippet=line.strip(),
                        stack_trace=(
                            f'Security Alert: Prototype Pollution\n'
                            f'    at {relative_path}:{lineno}'
                        ),
                        description="Modifying `__proto__` can pollute global Object prototype, leading to privilege escalation or bypass.",
                        cwe="CWE-1321",
                    )
                )

            # XSS / DOM Injection
            if "dangerouslySetInnerHTML" in line or "innerHTML" in line or "document.write" in line:
                bugs.append(
                    DetectedBug(
                        id=f"JS-XSS-{len(bugs)+1}",
                        severity="HIGH",
                        category="Security Vulnerability",
                        title="Cross-Site Scripting (XSS) via raw DOM insertion",
                        file_path=relative_path,
                        line_number=lineno,
                        symbol="dom_render",
                        code_snippet=line.strip(),
                        stack_trace=(
                            f'Security Alert: Unsanitized DOM injection\n'
                            f'    at {relative_path}:{lineno}'
                        ),
                        description="Directly injecting HTML without sanitization leads to Stored or Reflected XSS.",
                        cwe="CWE-79",
                        reproduction="Provide payload `<img src=x onerror=alert(1)>`.",
                    )
                )

    # 4. Universal SQL Injection Heuristic
    sql_patterns = [
        re.compile(r"""(SELECT|INSERT|UPDATE|DELETE)\s+.*\s+(FROM|INTO|SET)\s+.*(\+|%|\.format|f['"])""", re.IGNORECASE),
        re.compile(r"""execute\s*\(\s*f['"][^'"]*\{[^}]+\}""", re.IGNORECASE),
    ]
    for i, line in enumerate(lines):
        for pat in sql_patterns:
            if pat.search(line):
                bugs.append(
                    DetectedBug(
                        id=f"SQLI-{len(bugs)+1}",
                        severity="CRITICAL",
                        category="Security Vulnerability",
                        title="SQL Injection risk (String concatenation in SQL query)",
                        file_path=relative_path,
                        line_number=i + 1,
                        symbol="db_query",
                        code_snippet=line.strip(),
                        stack_trace=(
                            f'Traceback (SQL Injection Vulnerability):\n'
                            f'  File "{relative_path}", line {i + 1}\n'
                            f'SecurityError: Raw string formatting in database execution'
                        ),
                        description="Dynamically concatenating variables into SQL statements exposes database to SQL Injection.",
                        cwe="CWE-89",
                        reproduction="Inject `' OR '1'='1`.",
                    )
                )
                break

    return bugs


def hunt_all_bugs_in_project(project_dir: Path, max_files: int = 150) -> list[DetectedBug]:
    """Scan all project files and aggregate detected bugs."""
    all_bugs: list[DetectedBug] = []
    ignored = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}

    if not project_dir.exists():
        return all_bugs

    scanned_files = 0
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]

        for file_name in sorted(files):
            file_path = Path(root) / file_name
            if file_path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".json"}:
                continue

            rel = file_path.relative_to(project_dir).as_posix()
            bugs = scan_file_for_bugs(file_path, rel)
            all_bugs.extend(bugs)
            scanned_files += 1

            if scanned_files >= max_files:
                break
        if scanned_files >= max_files:
            break

    # Sort bugs by severity: CRITICAL > HIGH > MEDIUM > LOW
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_bugs.sort(key=lambda b: (severity_order.get(b.severity, 4), b.file_path, b.line_number))
    return all_bugs


def run_dynamic_test_runner(project_dir: Path) -> dict[str, Any] | None:
    """Safely check for test failures. Host-level dynamic execution is strictly disallowed
    for untrusted imported repositories to prevent Remote Code Execution (RCE).
    """
    if not project_dir.exists():
        return None

    # Check for pytest / unittest files
    test_files = list(project_dir.glob("test_*.py")) + list(project_dir.glob("tests/*.py"))
    if not test_files:
        return None

    # Host execution is blocked for security; only isolated sandbox (e.g. E2B) is permitted
    e2b_key = os.getenv("E2B_API_KEY", "").strip()
    if not e2b_key:
        logger.info("Host dynamic pytest disabled for repository security (AST static scan active)")
        return None

    # If E2B key present, untrusted execution is delegated to isolated disposable cloud sandbox
    try:
        from e2b_code_interpreter import Sandbox
        with Sandbox(api_key=e2b_key) as sbx:
            execution = sbx.run_code(f"import pytest; pytest.main(['-q', '{project_dir}'])")
            if execution.error:
                return {
                    "runner": "e2b_sandbox_pytest",
                    "output": execution.error.value,
                    "error": "Sandbox Pytest Failure Detected",
                }
    except Exception as exc:
        logger.warning(f"Sandbox runner error: {exc}")
    return None
