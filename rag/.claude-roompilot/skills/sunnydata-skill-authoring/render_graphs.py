#!/usr/bin/env python3
"""把某個 skill 的 SKILL.md 內所有 graphviz 流程圖輸出成 SVG。

用法：
    .venv-rag/bin/python render_graphs.py <skill-directory>           # 每張圖分開輸出
    .venv-rag/bin/python render_graphs.py <skill-directory> --combine # 所有圖合成一張

會抽出 SKILL.md 內所有 ```dot 區塊並用 graphviz 的 dot 指令渲染成 SVG，
方便把流程講給人類夥伴看。

需求：Python 3.11（本專案唯一環境 .venv-rag/）、系統已安裝 graphviz
      （macOS：brew install graphviz）

本檔取代原模板的 Node 腳本 render-graphs.js —— 本專案沒有 Node 生態。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ```dot 區塊；非貪婪以正確切出多張圖
DOT_BLOCK_RE = re.compile(r"```dot\n(.*?)```", re.DOTALL)
DIGRAPH_NAME_RE = re.compile(r"digraph\s+(\w+)")
DIGRAPH_BODY_RE = re.compile(r"digraph\s+\w+\s*\{(.*)\}", re.DOTALL)
RANKDIR_RE = re.compile(r"^\s*rankdir\s*=\s*\w+\s*;?\s*$", re.MULTILINE)


def extract_dot_blocks(markdown: str) -> list[dict[str, str]]:
    """回傳 [{'name': ..., 'content': ...}]；沒有 digraph 名稱時給流水號。"""
    blocks: list[dict[str, str]] = []
    for match in DOT_BLOCK_RE.finditer(markdown):
        content = match.group(1).strip()
        name_match = DIGRAPH_NAME_RE.search(content)
        name = name_match.group(1) if name_match else f"graph_{len(blocks) + 1}"
        blocks.append({"name": name, "content": content})
    return blocks


def extract_graph_body(dot_content: str) -> str:
    """只取出 digraph 的 body（節點與邊），並移除 rankdir（合併時統一在最外層設定）。"""
    match = DIGRAPH_BODY_RE.search(dot_content)
    if not match:
        return ""
    return RANKDIR_RE.sub("", match.group(1)).strip()


def combine_graphs(blocks: list[dict[str, str]], skill_name: str) -> str:
    """把多張圖包成 cluster 併進同一個 digraph，維持視覺分組。"""
    bodies = []
    for index, block in enumerate(blocks):
        body = extract_graph_body(block["content"])
        indented = "\n".join("    " + line for line in body.splitlines())
        bodies.append(f'  subgraph cluster_{index} {{\n    label="{block["name"]}";\n{indented}\n  }}')

    joined = "\n\n".join(bodies)
    return f"digraph {skill_name}_combined {{\n  rankdir=TB;\n  compound=true;\n  newrank=true;\n\n{joined}\n}}"


def render_to_svg(dot_content: str) -> str | None:
    """呼叫 dot -Tsvg；失敗時印出 stderr 並回傳 None（不讓整批中斷）。"""
    try:
        result = subprocess.run(
            ["dot", "-Tsvg"],
            input=dot_content,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        print(f"執行 dot 失敗：{err}", file=sys.stderr)
        if err.stderr:
            print(err.stderr, file=sys.stderr)
        return None
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把 skill 的 SKILL.md 內的 graphviz 流程圖渲染成 SVG",
        epilog=(
            "範例：\n"
            "  .venv-rag/bin/python render_graphs.py ../sunnydata-debugging\n"
            "  .venv-rag/bin/python render_graphs.py ../sunnydata-debugging --combine"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("skill_directory", help="skill 目錄（內含 SKILL.md）")
    parser.add_argument("--combine", action="store_true", help="所有流程圖合併成一張 SVG")
    args = parser.parse_args()

    skill_dir = Path(args.skill_directory).resolve()
    skill_file = skill_dir / "SKILL.md"
    skill_name = skill_dir.name.replace("-", "_")

    if not skill_file.is_file():
        print(f"錯誤：找不到 {skill_file}", file=sys.stderr)
        return 1

    # 先確認 graphviz 可用，錯誤訊息直接給安裝方式
    if shutil.which("dot") is None:
        print("錯誤：找不到 graphviz（dot）。安裝方式：", file=sys.stderr)
        print("  brew install graphviz    # macOS（本專案唯一目標平台）", file=sys.stderr)
        return 1

    markdown = skill_file.read_text(encoding="utf-8")
    blocks = extract_dot_blocks(markdown)

    if not blocks:
        print(f"{skill_file} 內找不到 ```dot 區塊")
        return 0

    print(f"在 {skill_dir.name}/SKILL.md 找到 {len(blocks)} 張圖")

    output_dir = skill_dir / "diagrams"
    output_dir.mkdir(exist_ok=True)

    if args.combine:
        combined = combine_graphs(blocks, skill_name)
        svg = render_to_svg(combined)
        if svg:
            (output_dir / f"{skill_name}_combined.svg").write_text(svg, encoding="utf-8")
            print(f"  已輸出：{skill_name}_combined.svg")

            # 一併留下 dot 原始碼，方便排查渲染問題
            (output_dir / f"{skill_name}_combined.dot").write_text(combined, encoding="utf-8")
            print(f"  原始碼：{skill_name}_combined.dot")
        else:
            print("  合併圖渲染失敗", file=sys.stderr)
    else:
        for block in blocks:
            svg = render_to_svg(block["content"])
            if svg:
                (output_dir / f"{block['name']}.svg").write_text(svg, encoding="utf-8")
                print(f"  已輸出：{block['name']}.svg")
            else:
                print(f"  失敗：{block['name']}", file=sys.stderr)

    print(f"\n輸出目錄：{output_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
