# Copyright 2025 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ruff: noqa: S405 (suspicious-xml-etree-import )

"""Generate source .rst files for lib tables, from CSV files in the reference directory."""

from __future__ import annotations

import csv
import pathlib
import typing
from xml.etree import ElementTree

####################
# Sphinx extension #
####################

if typing.TYPE_CHECKING:
    from typing import Iterable

    import sphinx.application


def setup(app: sphinx.application.Sphinx) -> dict[str, str | bool]:
    """Entrypoint for Sphinx extensions, connects generation code to Sphinx event."""
    app.connect('builder-inited', _generate)  # type: ignore
    return {'version': '1.0.0', 'parallel_read_safe': False, 'parallel_write_safe': False}


def _generate(app: sphinx.application.Sphinx):
    _generate_libs_tables(app.confdir)


####################
# Table generation #
####################


_EMOJIS = {
    # status
    'recommended': '✅',
    'dep': '↪️',
    'experimental': '⚗️',
    'legacy': '🪦',
    'team': '🚫',
    # substrate
    'machine': '🖥️',
    'K8s': '☸️',
}
_STATUS_TOOLTIPS = {
    'recommended': 'Recommended for use in new charms today!',
    'dep': 'Dependency of other libs, unlikely to be required directly.',
    'experimental': 'Experimental, use at your own risk!',
    'legacy': 'Not recommended, there are better alternatives available.',
    'team': 'Team internal lib, may not be stable for external use.',
}
_KIND_SORTKEYS = {'PyPI': 0, 'git': 1, 'Charmhub': 2, '': 3}
_STATUS_SORTKEYS = {'recommended': 0, '': 1, 'dep': 2, 'experimental': 3, 'legacy': 4, 'team': 5}
_FILE_HEADER = """..
    This file was automatically generated.
    It should not be manually edited!
    Instead, edit the corresponding -raw.csv file and then rebuild the docs.

"""
_REL_LIBS_TABLE_HEADER = """.. list-table::
   :class: sphinx-datatable
   :widths: 1, 40, 1, 60
   :header-rows: 1

   * -
     - Library
     - Kind
     - Interface
"""
_GEN_LIBS_TABLE_HEADER = """.. list-table::
   :class: sphinx-datatable
   :widths: 1, 40, 1, 60
   :header-rows: 1

   * -
     - Library
     - Kind
     - Description
"""
_KEY_TABLE_HEADER = """.. list-table::
   :widths: 1, 100
   :header-rows: 1

   * -
     - Description
"""


class _CSVRow(typing.TypedDict, total=True):
    name: str
    status: str
    url: str
    docs: str
    src: str
    kind: str
    description: str


class _RelCSVRow(_CSVRow, total=True):
    rel_name: str
    rel_url_charmhub: str
    rel_url_schema: str


class _GenCSVRow(_CSVRow, total=True):
    machine: str
    K8s: str


def _generate_libs_tables(docs_dir: str | pathlib.Path) -> None:
    ref_dir = pathlib.Path(docs_dir) / 'reference'
    gen_dir = ref_dir / 'generated'
    gen_dir.mkdir(exist_ok=True)
    # interface / relation libs
    with (ref_dir / 'libs-rel-raw.csv').open() as f:
        rel_entries: list[_RelCSVRow] = list(csv.DictReader(f))  # type: ignore
    rel_table = _get_rel_libs_table(rel_entries)
    _write_if_needed(path=(gen_dir / 'libs-rel-table.rst'), content=rel_table)
    # general / non-relation libs
    with (ref_dir / 'libs-non-rel-raw.csv').open() as f:
        non_rel_entries: list[_GenCSVRow] = list(csv.DictReader(f))  # type: ignore
    non_rel_table = _get_gen_libs_table(non_rel_entries)
    _write_if_needed(path=(gen_dir / 'libs-non-rel-table.rst'), content=non_rel_table)
    # status key
    key_table = _get_status_key_table()
    msg = ' Library status is shown in the left column. See tooltips, or click here for a key.'
    content = f'.. dropdown::{msg}\n\n' + '\n'.join('   ' + line for line in key_table.split('\n'))
    _write_if_needed(path=(gen_dir / 'status-key-table.rst'), content=content)


def _write_if_needed(path: pathlib.Path, content: str) -> None:
    """Write to path only if contents are different.

    This allows sphinx-build to skip rebuilding pages that depend on the output of this extension
    if the output hasn't actually changed.
    """
    to_write = _FILE_HEADER + content
    if not path.exists() or path.read_text() != to_write:
        path.write_text(to_write)


##########
# tables #
##########


def _get_rel_libs_table(entries: list[_RelCSVRow]) -> str:
    def key(row: tuple[str, ...]) -> tuple[str, ...]:
        status, _name, _kind, desc = row
        return status, desc

    rows = [(_status(e), _name(e), _kind(e), _rel_description(e)) for e in entries]
    return _REL_LIBS_TABLE_HEADER + _rst_rows(sorted(rows, key=key))


def _get_gen_libs_table(entries: list[_GenCSVRow]) -> str:
    def key(row: tuple[str, ...]) -> tuple[str, ...]:
        status, _name, kind, desc = row
        return status, kind, desc

    rows = [(_status(e), _name(e), _kind(e), _gen_description(e)) for e in entries]
    return _GEN_LIBS_TABLE_HEADER + _rst_rows(sorted(rows, key=key))


def _get_status_key_table() -> str:
    rows = [
        (_status({'status': s}), _STATUS_TOOLTIPS[s])  # type: ignore
        for s in _STATUS_SORTKEYS
        if s in _EMOJIS
    ]
    rows.append(('', 'None of the above.'))
    return _KEY_TABLE_HEADER + _rst_rows(rows)


##########
# fields #
##########


def _status(entry: _CSVRow) -> str:
    status = entry['status']
    html_lines = [_html_hidden_span(_STATUS_SORTKEYS[status])]
    if status in _EMOJIS:
        html_lines.append(_html_emoji_tooltip(_EMOJIS[status], _STATUS_TOOLTIPS.get(status)))
    return _rst_table_indent(_rst_raw_html('\n'.join(html_lines)))


def _name(entry: _CSVRow) -> str:
    main_link = _html_link(entry['name'], entry['url'])
    extra_links = ', '.join([
        _html_link(_EMOJIS.get(text, '') + text, url)
        for text in ('docs', 'src')
        if (url := entry[text])
    ])
    html = f'{main_link} ({extra_links})' if extra_links else main_link
    return _rst_table_indent(_rst_raw_html(html))


def _kind(entry: _CSVRow) -> str:
    kind = entry['kind']
    content = [_rst_raw_html(_html_hidden_span(_KIND_SORTKEYS[kind]))]
    if kind_str := _EMOJIS.get(kind, '') + kind:
        content.append(_rst_lines(kind_str))
    return _rst_table_indent('\n'.join(content))


def _rel_description(entry: _RelCSVRow) -> str:
    sortkeys = [
        entry['rel_name'].ljust(64, 'z'),
        str(_STATUS_SORTKEYS[entry['status']]),
        entry['name'],
        str(_KIND_SORTKEYS[entry['kind']]),
    ]
    html_lines = [_html_hidden_span(''.join(sortkeys))]
    if rel_links := _rel_links(entry):
        html_lines.append(rel_links)
    content = [_rst_raw_html('\n'.join(html_lines))]
    if desc := entry['description']:
        content.append(_rst_lines(desc))
    return _rst_table_indent('\n'.join(content))


def _rel_links(entry: _RelCSVRow) -> str:
    if not (name := entry['rel_name']):
        return ''
    if not (main_url := entry['rel_url_charmhub']):
        return _html_no_spellcheck_span(name)
    main_link = _html_link(name, main_url)
    if not (schema_url := entry['rel_url_schema']):
        return main_link
    schema_link = _html_link('schema', schema_url)
    return f'{main_link} ({schema_link})'


def _gen_description(entry: _GenCSVRow) -> str:
    substrates = ('machine', 'K8s')
    sortkeys = [
        *('0' if entry[s] else '1' for s in substrates),
        str(_STATUS_SORTKEYS[entry['status']]),
        entry['name'],
        str(_KIND_SORTKEYS[entry['kind']]),
    ]
    content = [_rst_raw_html(_html_hidden_span(''.join(sortkeys)))]
    if firstline := ' '.join(_EMOJIS.get(s, '') + s for s in substrates if entry[s]):
        content.append(_rst_lines(firstline))
    if desc := entry['description']:
        content.append(_rst_lines(desc))
    return _rst_table_indent('\n'.join(content))


#######
# rst #
#######


def _rst_rows(rows: Iterable[tuple[str, ...]]) -> str:
    lines: list[str] = []
    for row in rows:
        first, *rest = (f' {cell}' if cell and not cell.startswith('\n') else cell for cell in row)
        lines.append(f'   * -{first}\n')
        lines.extend(f'     -{line}\n' for line in rest)
    return ''.join(lines)


def _rst_raw_html(html: str) -> str:
    return f"""
.. raw:: html

{_indent_lines(html, level=3)}
"""


def _rst_lines(text: str) -> str:
    return '\n'.join(f'| {line}' if line else '|' for line in text.split('\n'))


def _rst_table_indent(text: str) -> str:
    return _indent_lines(text, level=7)


def _indent_lines(text: str, *, level: int) -> str:
    indent = ' ' * level
    return '\n'.join(f'{indent}{line}' if line else '' for line in text.split('\n'))


########
# html #
########


def _html_emoji_tooltip(emoji: str, tooltip: str | None) -> str:
    e = ElementTree.Element('div', attrib={'class': 'emoji-div'})
    e.text = emoji
    if tooltip is not None:
        child = ElementTree.Element('div', attrib={'class': 'emoji-tooltip'})
        child.text = tooltip
        e.append(child)
    return ElementTree.tostring(e, encoding='unicode')


def _html_hidden_span(text: object) -> str:
    e = ElementTree.Element('span', attrib={'style': 'display:none;', 'class': 'no-spellcheck'})
    e.text = str(text)
    return ElementTree.tostring(e, encoding='unicode')


def _html_link(text: str, url: str) -> str:
    e = ElementTree.Element('a', attrib={'href': url, 'class': 'no-spellcheck'})
    e.text = text
    return ElementTree.tostring(e, encoding='unicode')


def _html_no_spellcheck_span(text: object) -> str:
    e = ElementTree.Element('span', attrib={'class': 'no-spellcheck'})
    e.text = str(text)
    return ElementTree.tostring(e, encoding='unicode')
