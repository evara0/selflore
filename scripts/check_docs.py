"""Check repository-local links in tracked, current public Markdown only."""
from __future__ import annotations

import argparse
from collections import Counter
from html import unescape
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import unquote, urlsplit


def tracked_paths(root: Path) -> set[str]:
    data = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z'])
    return {p.decode('utf-8') for p in data.split(b'\0') if p}


def prose(text: str, preserve_inline: bool = False) -> str:
    """Drop fenced/inline code, including the indented fences used in lists."""
    lines: list[str] = []
    fence = ''
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            marker = match.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ''
            continue
        if not fence:
            lines.append(re.sub(r'(`+)(.*?)\1', r'\2' if preserve_inline else '', line))
    if fence:
        raise ValueError('unclosed Markdown fence')
    return '\n'.join(lines)


def heading_ids(text: str) -> set[str]:
    counts: Counter[str] = Counter()
    identifiers: set[str] = set()
    # Preserve inline code text in headings, unlike link scanning.
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', prose(text, preserve_inline=True), re.M):
        heading = re.sub(r'<[^>]+>', '', unescape(heading)).lower()
        slug = ''.join(c for c in heading if c in '_-' or c.isspace() or unicodedata.category(c)[0] in 'LN')
        slug = slug.replace(' ', '-')
        number = counts[slug]
        counts[slug] += 1
        identifiers.add(slug + (f'-{number}' if number else ''))
    return identifiers


def destinations(text: str) -> list[str]:
    text = prose(text)
    references = {name.casefold(): target for name, target in
                  re.findall(r'^\s*\[([^\]]+)\]:\s*(<[^>]+>|\S+)', text, re.M)}
    targets = re.findall(r'!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+["\'][^\n]*?["\'])?\s*\)', text)
    for label, reference in re.findall(r'!?\[([^\]\n]+)\]\[([^\]\n]*)\]', text):
        key = (reference or label).casefold()
        if key not in references:
            raise ValueError(f'undefined Markdown link reference: {reference or label}')
        targets.append(references[key])
    return [unescape(target.strip('<>')) for target in targets]


def check(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    tracked = tracked_paths(root)
    errors: list[str] = []
    total = 0
    sources = sorted(p for p in tracked if p.endswith('.md') and not p.startswith('openspec/'))
    for name in sources:
        source = root / name
        if not source.resolve().is_relative_to(root):
            errors.append(f'{name}: Markdown source outside repository')
            continue
        try:
            targets = destinations(source.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as error:
            errors.append(f'{name}: {error}')
            continue
        for target in targets:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                if parsed.scheme not in {'http', 'https', 'mailto', 'tel'} and not parsed.netloc:
                    errors.append(f'{name}: unsupported link scheme: {target}')
                continue
            total += 1
            if parsed.path.startswith('/'):
                errors.append(f'{name}: use a repository-relative link: {target}')
                continue
            destination = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source.resolve()
            if not destination.is_relative_to(root):
                errors.append(f'{name}: target outside repository: {target}')
                continue
            relative = destination.relative_to(root).as_posix()
            is_file = relative in tracked and destination.is_file()
            is_directory = destination.is_dir() and any(p.startswith(relative + '/') for p in tracked)
            if not (is_file or is_directory):
                errors.append(f'{name}: missing or untracked target: {target}')
            elif parsed.fragment:
                if not is_file or destination.suffix.lower() != '.md':
                    errors.append(f'{name}: unsupported local fragment: {target}')
                elif unquote(parsed.fragment) not in heading_ids(destination.read_text(encoding='utf-8-sig')):
                    errors.append(f'{name}: missing heading: {target}')
    return total, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    total, errors = check(args.root)
    for error in errors:
        print(error)
    print(f'Public Markdown: {total} local links checked; {len(errors)} errors')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
