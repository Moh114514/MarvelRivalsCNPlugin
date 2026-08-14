"""Visual command guide page."""

from __future__ import annotations

from collections.abc import Iterable

from ..components import page_header, page_shell, section_title
from ..formatters import escape_text


def _parse_help_text(help_text: str) -> tuple[list[tuple[str, str]], list[str]]:
    lines = [line.strip() for line in help_text.strip().splitlines()]
    commands: list[tuple[str, str]] = []
    notes: list[str] = []
    index = 1 if lines else 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue
        if line.startswith("/"):
            description = ""
            next_index = index + 1
            while next_index < len(lines) and not lines[next_index]:
                next_index += 1
            if next_index < len(lines) and not lines[next_index].startswith("/"):
                description = lines[next_index]
                index = next_index + 1
            else:
                index = next_index
            commands.append((line, description))
            continue
        notes.append(line)
        index += 1
    return commands, notes


def _command_rows(commands: Iterable[tuple[str, str]]) -> str:
    return "".join(
        '<article class="mr-command-row">'
        f'<strong class="mr-command-row__command">{escape_text(command)}</strong>'
        f'<span class="mr-command-row__description">{escape_text(description)}</span>'
        '</article>'
        for command, description in commands
    )


def build_help_html(help_text: str) -> str:
    """Render the plugin's existing help text as a themed image page."""

    commands, notes = _parse_help_text(help_text)
    note_html = "".join(
        f'<p class="mr-help-note">{escape_text(note)}</p>' for note in notes
    )
    content = (
        page_header(
            "COMMAND GUIDE",
            "漫威争锋查询指令",
            "HELP",
            title_cn="指令帮助",
            eyebrow="MR // GUIDE",
        )
        + '<section class="mr-section">'
        + section_title("可用指令", "COMMANDS")
        + f'<div class="mr-command-list">{_command_rows(commands)}</div>'
        + note_html
        + '</section>'
    )
    return page_shell(content, watermark="COMMAND GUIDE")
