"""Size and shape of the code, measured rather than felt.

Feeds the maintainability half of the audit: the project's own rules put
a function over 50 lines or past 3 nesting levels in the "too many
things" bucket, and this says which ones those are.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def py_report(path: Path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    rows = []

    def depth(node, d=0):
        # An `elif` is an If nested in the parent's `orelse`, so a flat
        # 22-branch dispatch measured as 22 levels of nesting in the
        # first version of this script. A chain is one level.
        best = d
        for field, child in ast.iter_fields(node):
            kids = child if isinstance(child, list) else [child]
            for kid in kids:
                if not isinstance(kid, ast.AST):
                    continue
                chained = field == "orelse" and isinstance(node, ast.If) and isinstance(kid, ast.If)
                nd = (
                    d
                    if chained
                    else (d + 1 if isinstance(kid, (ast.If, ast.For, ast.While, ast.With, ast.Try)) else d)
                )
                best = max(best, depth(kid, nd))
        return best

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            branches = sum(
                isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp)) for n in ast.walk(node)
            )
            rows.append((length, depth(node), branches, node.name, node.lineno))
    return src, tree, rows


src, tree, rows = py_report(ROOT / "src/oku/cli.py")
print(f"cli.py: {len(src.splitlines())} lines, {len(rows)} functions")
print(
    f"  over 50 lines: {sum(1 for r in rows if r[0] > 50)}   over 100: {sum(1 for r in rows if r[0] > 100)}"
)
print("  longest:")
for length, d, br, name, line in sorted(rows, reverse=True)[:12]:
    print(f"    {length:5} lines  depth {d}  branches {br:4}  {name}  (cli.py:{line})")

# Module-level names assigned more than once: the shadowing shape.
assigns = {}
for node in tree.body:
    targets = []
    if isinstance(node, ast.Assign):
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
    elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        targets = [node.name]
    for t in targets:
        assigns.setdefault(t, []).append(node.lineno)
dupes = {k: v for k, v in assigns.items() if len(v) > 1}
print(f"\n  module-level names bound more than once: {len(dupes)}")
for k, v in sorted(dupes.items()):
    print(f"    {k}: lines {v}")

for js in ("kit/chrome.js", "kit/renderer.js"):
    text = (ROOT / js).read_text(encoding="utf-8")
    lines = text.splitlines()
    # Top-level `function name(` blocks, closed by a column-0 '}'.
    funcs, cur = [], None
    for i, line in enumerate(lines, 1):
        m = (
            re.match(r"^(?:async )?function ([A-Za-z_$][\w$]*)", line)
            or re.match(r"^(?:const|let|var) ([A-Za-z_$][\w$]*) = (?:async )?(?:function|\()", line)
            or re.match(r"^ {2}([A-Za-z_$][\w$]*)\(.*\) \{$", line)
        )
        if m:
            cur = (m.group(1), i)
        elif cur and line.startswith("}"):
            funcs.append((i - cur[1] + 1, cur[0], cur[1]))
            cur = None
    print(f"\n{js}: {len(lines)} lines, {len(funcs)} top-level functions")
    print(
        f"  over 100 lines: {sum(1 for f in funcs if f[0] > 100)}   over 300: {sum(1 for f in funcs if f[0] > 300)}"
    )
    for length, name, line in sorted(funcs, reverse=True)[:8]:
        print(f"    {length:5} lines  {name}  ({js}:{line})")

css = (ROOT / "kit/chrome.css").read_text(encoding="utf-8")
print(
    f"\nchrome.css: {len(css.splitlines())} lines, {css.count('{')} blocks, "
    f"{css.count('!important')} !important, {len(re.findall(r'@media', css))} media queries"
)
