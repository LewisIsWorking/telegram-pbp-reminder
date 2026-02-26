"""Post the latest CHANGELOG.md entry to a Telegram topic.

Usage (via GitHub Actions or manually):
    TELEGRAM_BOT_TOKEN=xxx python scripts/post_changelog.py

Reads the latest version block from CHANGELOG.md, formats it for Telegram,
and posts it to the configured topic. Skips if no token is set.
"""

import os
import re
import sys
import requests
from pathlib import Path

# ---- Configuration ----
# Foundry & GitHub: feedback, improvements, questions, etc.
# https://t.me/Path_Wars/71537
CHANGELOG_CHAT_ID = os.environ.get("CHANGELOG_CHAT_ID", "@Path_Wars")
CHANGELOG_THREAD_ID = int(os.environ.get("CHANGELOG_THREAD_ID", "71537"))
TELEGRAM_MAX_LENGTH = 4096


def read_latest_entry(changelog_path: Path) -> tuple[str, str]:
    """Extract the latest version entry from CHANGELOG.md.

    Returns (version_header, body) where version_header is like '## [1.0.0] - 2026-02-26'
    and body is everything until the next ## header or end of file.
    """
    text = changelog_path.read_text(encoding="utf-8")

    # Find all ## [x.y.z] headers
    pattern = r"^(## \[.+?\].*?)(?=\n## \[|\Z)"
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)

    if not matches:
        return "", ""

    latest = matches[0].strip()

    # Split header from body
    lines = latest.split("\n", 1)
    header = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    return header, body


def markdown_to_telegram(header: str, body: str) -> str:
    """Convert changelog markdown to Telegram-friendly format.

    Telegram supports a subset of HTML. We convert:
    - ### headers to bold text
    - **bold** to <b>bold</b>
    - *italic* to <i>italic</i>
    - `code` to <code>code</code>
    - Preserves line breaks and list structure
    """
    # Extract version from header: ## [1.0.0] - 2026-02-26
    version_match = re.search(r"\[(.+?)\]", header)
    version = version_match.group(1) if version_match else "Unknown"

    date_match = re.search(r"\d{4}-\d{2}-\d{2}", header)
    date_str = date_match.group(0) if date_match else ""

    # Title line
    title = f"🤖 <b>PBP Reminder Bot v{version}</b>"
    if date_str:
        title += f"  ({date_str})"

    # Process body
    lines = body.split("\n")
    processed = []

    for line in lines:
        # Skip the "### Summary" header itself but keep its content
        if line.startswith("### "):
            section_name = line.replace("### ", "").strip()
            processed.append(f"\n<b>{section_name}</b>")
            continue

        # Bold: **text** -> <b>text</b>
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)

        # Italic: *text* -> <i>text</i> (but not inside bold tags)
        line = re.sub(r"(?<!</b>)\*(.+?)\*", r"<i>\1</i>", line)

        # Inline code: `text` -> <code>text</code>
        line = re.sub(r"`(.+?)`", r"<code>\1</code>", line)

        # Escape HTML in remaining text (but not our tags)
        # (Skip this since our input is controlled markdown)

        processed.append(line)

    result = title + "\n" + "\n".join(processed)

    # Clean up excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit.

    Splits on paragraph boundaries (double newlines) when possible.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            # If a single paragraph exceeds the limit, split on single newlines
            if len(paragraph) > max_length:
                for line in paragraph.split("\n"):
                    line_candidate = f"{current}\n{line}" if current else line
                    if len(line_candidate) <= max_length:
                        current = line_candidate
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = line
            else:
                current = paragraph

    if current:
        chunks.append(current.strip())

    return chunks


def post_to_telegram(text: str, token: str) -> bool:
    """Post a message to the configured Telegram topic. Returns True on success."""
    chunks = split_message(text)
    success = True

    for i, chunk in enumerate(chunks):
        if i > 0:
            chunk = f"(continued)\n\n{chunk}"

        payload = {
            "chat_id": CHANGELOG_CHAT_ID,
            "message_thread_id": CHANGELOG_THREAD_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                print(f"Posted chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)")
            else:
                print(f"Telegram error: {resp.text[:300]}")
                success = False
        except requests.RequestException as e:
            print(f"Network error: {e}")
            success = False

    return success


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("No TELEGRAM_BOT_TOKEN set, skipping changelog post")
        return 0

    changelog_path = Path(__file__).parent.parent / "CHANGELOG.md"
    if not changelog_path.exists():
        print("No CHANGELOG.md found, skipping")
        return 0

    header, body = read_latest_entry(changelog_path)
    if not header:
        print("No version entry found in CHANGELOG.md, skipping")
        return 0

    message = markdown_to_telegram(header, body)
    print(f"Posting changelog ({len(message)} chars):")
    print(message[:200] + "..." if len(message) > 200 else message)
    print()

    if post_to_telegram(message, token):
        print("Changelog posted successfully")
        return 0
    else:
        print("Failed to post changelog")
        return 1


if __name__ == "__main__":
    sys.exit(main())
