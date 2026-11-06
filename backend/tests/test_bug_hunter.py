"""Test suite for deep Bug Hunter and Patch Review Rubric."""

from pathlib import Path
import tempfile
from agents.bug_hunter import PythonAstHunter, scan_file_for_bugs, hunt_all_bugs_in_project
from agents.reviewer import evaluate_patch_rubric


def test_ast_hunter_detects_bugs():
    source = """
def leaky_func(items=[]):
    try:
        x = 10 / (1 - discount)
        eval("2 + 2")
    except:
        pass
"""
    hunter = PythonAstHunter("service.py", source)
    import ast
    hunter.visit(ast.parse(source))
    
    categories = {b.category for b in hunter.bugs}
    assert "Logic Error" in categories  # mutable default
    assert "ZeroDivision / Crash" in categories  # division by (1 - discount)
    assert "Security Vulnerability" in categories  # eval()
    assert "Unhandled Exception" in categories  # bare except: pass


def test_secret_and_js_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        js_file = Path(tmpdir) / "app.js"
        js_file.write_text("""
function handlePayload(req) {
    req.__proto__.isAdmin = true;
    document.getElementById("output").innerHTML = req.input;
}
""", encoding="utf-8")
        
        bugs = scan_file_for_bugs(js_file, "app.js")
        titles = [b.title for b in bugs]
        assert any("Prototype Pollution" in t for t in titles)
        assert any("Cross-Site Scripting" in t for t in titles)


def test_evaluate_patch_rubric_clean():
    original = "def calc(a, b):\n    return a / (1 - b)\n"
    patched = "def calc(a, b):\n    if b == 1:\n        return 0\n    return a * (1 - b)\n"
    rubric = evaluate_patch_rubric(original, patched, "calc.py")
    assert rubric["total"] >= 85
    assert rubric["security"] == 25
    assert rubric["syntax_integrity"] == 20
