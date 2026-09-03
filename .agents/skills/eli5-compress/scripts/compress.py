#!/usr/bin/env python3
"""
ELI5 Compress Orchestrator

Usage:
    python -m scripts <filepath>
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import List

from .detect import should_compress
from .validate import validate

MAX_FILE_SIZE = 100_000  # 100 KB
MAX_FIX_ATTEMPTS = 2


# ---------- Claude Calls ----------


def call_claude(prompt: str) -> str:
    try:
        result = subprocess.run(
            ["claude", "--print"],
            input=prompt,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Claude call failed:\n{e.stderr}")


_FENCE_RE = re.compile(r"^(`{3,})[^\n]*\n(.*)\n\1\s*$", re.DOTALL)


def strip_markdown_wrapper(text: str) -> str:
    """Remove outer ```markdown ... ``` wrapper that Claude sometimes adds."""
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        return m.group(2).strip()
    return text


def build_compress_prompt(original: str) -> str:
    return f"""Aggressively compress this markdown. Shortest possible text, same meaning.

CUT:
- Filler: just, really, basically, actually, simply, essentially, generally, pretty much, significantly
- Pleasantries: sure, certainly, of course, happy to, I'd recommend, please note, you should
- Hedging: might be worth, could consider, would be good to, it's important to, it is recommended
- Redundant phrases: "in order to" → "to", "make sure" → drop, "the reason is because" → "because", "be aware" → drop, "keep in mind" → drop, "this means that" → drop
- Connectives: however, furthermore, additionally, moreover, in addition, as a result
- Formal bloat: "ensure that" → drop, "utilize" → "use", "implement" → "add", "This approach was chosen" → drop
- Justifications: drop "because X" if the instruction stands alone without it
- Repetition: if two sentences say the same thing, keep ONLY the shorter one
- Context that readers already know: "The application requires..." → just list what's needed

REWRITE into fragments:
- "When you receive a 401 response, you should attempt to refresh" → "On 401 → refresh"
- "The client tries to reconnect with an expired token before the refresh completes" → "Client reconnects before refresh completes"
- "Users have requested keyboard shortcuts for creating new tasks (Ctrl+N), searching (Ctrl+K)" → "Shortcuts: Ctrl+N (new), Ctrl+K (search)"
- Multi-sentence explanations → single fragment. Two sentences → one wherever possible
- Drop articles (a/an/the) aggressively
- Use symbols: → & + / instead of words
- Collapse enumerations: "controllers handle HTTP, services contain logic, repos manage DB" → "controller → service → repo pattern"

NEVER MODIFY (preserve exactly):
- Code blocks (fenced ``` and indented)
- Inline code (`backtick content`)
- URLs, links, file paths, commands
- Headings (exact text)
- Version numbers, dates, numeric values
- Technical terms, library names, API names

EXAMPLES:
Not: "I strongly prefer TypeScript with strict mode enabled for all new code. Please don't use any type unless there's genuinely no way around it, and if you do, leave a comment."
Yes: "TypeScript strict mode. No `any` unless unavoidable — comment why."

Not: "The real-time collaboration feature sometimes fails to reconnect after a network interruption. The client-side reconnection logic has a race condition with the authentication refresh flow. Tracked in issue TF-456."
Yes: "Reconnection races auth refresh after network drop (TF-456)."

Not: "This approach was chosen over offset-based pagination because it provides consistent results even when items are being added or removed concurrently."
Yes: "Cursor-based pagination — stable during concurrent changes."

Return ONLY the compressed text. No explanation, no wrapper.

<TEXT>
{original}
</TEXT>
"""


def build_fix_prompt(original: str, compressed: str, errors: List[str]) -> str:
    errors_str = "\n".join(f"- {e}" for e in errors)
    return f"""You are fixing a compressed markdown file. Specific validation errors were found.

CRITICAL RULES:
- DO NOT recompress or rephrase the file
- ONLY fix the listed errors — leave everything else exactly as-is
- The ORIGINAL is provided as reference only (to restore missing content)
- Preserve the simplified style in all untouched sections

ERRORS TO FIX:
{errors_str}

HOW TO FIX:
- Missing URL: find it in ORIGINAL, restore it exactly where it belongs in COMPRESSED
- Code block mismatch: find the exact code block in ORIGINAL, restore it in COMPRESSED
- Heading mismatch: restore the exact heading text from ORIGINAL into COMPRESSED
- Do not touch any section not mentioned in the errors

Return ONLY the fixed compressed file. No explanation.

<ORIGINAL>
{original}
</ORIGINAL>

<COMPRESSED>
{compressed}
</COMPRESSED>
"""


# ---------- Core Logic ----------


def compress_file(filepath: Path) -> bool:
    print(f"Processing: {filepath}")

    if not should_compress(filepath):
        print("Skipping (not natural language)")
        return False

    original_text = filepath.read_text(errors="ignore")

    if not original_text.strip():
        print("Skipping (file is empty)")
        return False

    file_size = filepath.stat().st_size
    if file_size > MAX_FILE_SIZE:
        print(f"Skipping (file too large: {file_size} bytes, max {MAX_FILE_SIZE})")
        return False

    backup_path = filepath.with_name(filepath.stem + ".original.md")

    # Step 1: Compress
    print("Simplifying with Claude...")
    compressed = strip_markdown_wrapper(call_claude(build_compress_prompt(original_text)))

    if not compressed.strip():
        print("Skipping (Claude returned empty response)")
        return False

    # Save original as backup (only if no backup exists yet)
    if not backup_path.exists():
        backup_path.write_text(original_text)
    filepath.write_text(compressed)

    # Step 2: Validate + fix loop
    for fix_attempt in range(MAX_FIX_ATTEMPTS + 1):
        print(f"\nValidation attempt {fix_attempt + 1}")

        result = validate(backup_path, filepath)

        if result.is_valid:
            print("Validation passed")
            return True

        print("Validation failed:")
        for err in result.errors:
            print(f"   - {err}")

        if fix_attempt == MAX_FIX_ATTEMPTS:
            break

        print("Fixing with Claude...")
        compressed = strip_markdown_wrapper(
            call_claude(build_fix_prompt(original_text, compressed, result.errors))
        )
        filepath.write_text(compressed)

    # All fix attempts exhausted — restore original
    filepath.write_text(original_text)
    backup_path.unlink(missing_ok=True)
    print("Failed after retries — original restored")
    return False


# ---------- Main ----------


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m scripts <filepath>")
        sys.exit(1)

    filepath = Path(sys.argv[1])

    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    success = compress_file(filepath)

    if success:
        sys.exit(0)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
