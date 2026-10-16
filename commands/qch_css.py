#   Copyright (C) 2026  Cristian Adam <cristian.adam@gmail.com>
#
#   This file is part of openjdk-doc
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see http://www.gnu.org/licenses/.

# Builds the stylesheets the Qt Help (.qch) rendition of the documentation
# links.
#
# javadoc's own stylesheet is written almost entirely against custom
# properties: fifty-six of them are declared in one `:root` block and every
# color, font and font size in the sheet is a `var()` of one.  That is the
# whole of the dark scheme here.  The sheet is read once and written out
# twice, with the variables resolved -- `qch-dark.css` says what the
# fifty-six become on a dark page, and nothing else has to be touched for the
# pages to follow.
#
# Resolving them rather than leaving the `var()`s for the viewer is
# deliberate: which litehtml a help viewer was built against is not something
# the archive can know, and a `var()` that goes unresolved is not a color
# that is slightly off but no declaration at all.  Flattening costs us
# nothing -- the variables are set once, at the root, and never shadowed.
#
# Three files are written, because of the names the viewers go looking for.
# Asked for `offline-simple.css`, Qt Assistant and Qt Creator both serve
# `offline-dark.css` in its place when their own theme is dark, and
# `offline.css` when it is light.  The pages here ask for
# `offline-simple.css`, and the light sheet is written under both of the
# other names so that whichever one a viewer reaches for is there.
#
# What is dropped on the way out is what litehtml does not lay out: `display:
# grid`, which every summary table was built on until `qch_html` turned them
# back into tables, and the sticky positioning of a navigation bar that is no
# longer on the page.  The responsive rules go too: they are keyed to the
# window width, and a help pane is narrow enough to be mistaken for a phone.

import os
import re

# The stylesheets of the bundle: the API documentation has javadoc's, and the
# specifications and the manual pages share one of their own.  Each is looked
# for in turn and the first one that is there is the one used -- javadoc kept
# its stylesheet beside the pages until it gathered the generated resources
# into `resource-files` in JDK 22.
API_DIR = 'api'
ZONE_API = 'api'
ZONE_SHARED = 'shared'

CSS_SOURCES = {
    ZONE_API: [os.path.join('api', 'resource-files', 'stylesheet.css'),
               os.path.join('api', 'stylesheet.css')],
    ZONE_SHARED: [os.path.join('resources', 'jdk-default.css')],
}

# Ours, which each of those is written out as.
LINKED_CSS_NAME = 'offline-simple.css'
LIGHT_CSS_NAMES = ['offline.css', 'offline-simple.css']
DARK_CSS_NAME = 'offline-dark.css'

# The stylesheets kept at the root of the source tree: `qch-viewer.css` fits
# the pages to a help pane, `qch-dark.css` carries the dark palette.  Both
# are read for a `:root` block, which sets the variables the generated sheet
# is resolved against, and for whatever rules follow it, which are appended.
ASSET_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER_CSS = 'qch-viewer.css'
DARK_CSS = 'qch-dark.css'

COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)
IMPORT_RE = re.compile(r'@import[^;]*;')
ROOT_RE = re.compile(r':root\s*\{(.*?)\}', re.S)
CUSTOM_PROPERTY_RE = re.compile(r'(--[\w-]+)\s*:\s*([^;]*)')

# `var(--name)` or `var(--name, fallback)`, where the fallback may itself
# hold a `var()` and therefore a nested pair of parentheses.
VAR_RE = re.compile(
    r'var\(\s*(--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)')

# How deep a variable may be defined in terms of another before we call it a
# cycle.  javadoc nests them two deep.
MAX_VAR_DEPTH = 8


# -- custom properties -----------------------------------------------------

def read_root_variables(css_text):
    # The custom properties a sheet declares, with each value left as it was
    # written: one may name another, and which value that comes out as
    # depends on the sheet it is resolved against rather than this one.
    variables = {}
    for block in ROOT_RE.findall(css_text):
        for name, value in CUSTOM_PROPERTY_RE.findall(block):
            variables[name] = value.strip()
    return variables


def resolve_value(value, variables, depth=0):
    # The value with every `var()` in it replaced by what the variable comes
    # out as.  A variable that is not declared falls back to whatever the
    # `var()` names as its second argument, and failing that to nothing --
    # which is what a browser does with it as well.
    if depth >= MAX_VAR_DEPTH or 'var(' not in value:
        return value

    def replace(match):
        name, fallback = match.group(1), match.group(2)
        if name in variables:
            return resolve_value(variables[name], variables, depth + 1)
        if fallback is not None:
            return resolve_value(fallback.strip(), variables, depth + 1)
        return ''

    return resolve_value(VAR_RE.sub(replace, value), variables, depth + 1)


# -- what a help viewer cannot lay out -------------------------------------

# Properties dropped outright: the grid the summary tables were built on, and
# the gaps and spans that go with it.  `qch_html` has turned those tables
# into real ones by the time a page reaches a viewer, so the declarations
# would only describe a layout that is no longer there -- and a `display`
# litehtml does not know is worse than none, since it takes the element out
# of the flow it would otherwise have had.
DROPPED_PROPERTY_RE = re.compile(
    r'^(grid[\w-]*|gap|row-gap|column-gap|backdrop-filter|filter)$')

DROPPED_VALUES = {
    'display': re.compile(r'^(inline-)?(grid|flex)$'),
    'position': re.compile(r'^(sticky|fixed)$'),
}

# The media queries that survive.  The responsive ones are keyed to the
# window width and a help pane is narrow, so they would fire on a desktop and
# collapse the page to its phone layout; the print rules are kept, since a
# reader printing from the help viewer wants the page as it was meant to be.
MEDIA_FEATURE_RE = re.compile(r'\(\s*(?:max|min)-width')


def keep_media(prelude):
    return not MEDIA_FEATURE_RE.search(prelude)


# -- font sizes ------------------------------------------------------------

# javadoc sizes the page in pixels: a 14.2px body, a 14px code font.  A help
# pane starts from the font the reader chose for it, so the sizes are
# restated as proportions of that -- `qch-viewer.css` sets the four variables
# the sheet works from, and the handful of lengths the sheet states outright
# are converted here, against the body size javadoc assumed.
JAVADOC_BODY_PX = 14.2

FONT_SIZE_RE = re.compile(r'^([0-9]*\.?[0-9]+)\s*(px|rem)$', re.IGNORECASE)


def relative_font_size(value):
    match = FONT_SIZE_RE.match(value.strip())
    if match is None:
        return value

    number, unit = float(match.group(1)), match.group(2).lower()
    # A `rem` is already a proportion, of a root the reader now sets.
    size = number if unit == 'rem' else number / JAVADOC_BODY_PX
    return '%.4gem' % size


# -- the sheet -------------------------------------------------------------

def split_declarations(body):
    # A rule's declarations.  Splitting on every semicolon would do, were it
    # not for the sort arrows of the sortable tables: those are an inline SVG
    # in a `data:` URL, and `data:image/svg+xml; utf8, ...` carries one of
    # its own.  So a semicolon inside quotes or parentheses is passed over.
    parts = []
    current = []
    depth = 0
    quote = None

    for character in body:
        if quote is not None:
            current.append(character)
            if character == quote:
                quote = None
            continue

        if character in '"\'':
            quote = character
        elif character == '(':
            depth += 1
        elif character == ')':
            depth = max(depth - 1, 0)
        elif character == ';' and depth == 0:
            parts.append(''.join(current))
            current = []
            continue

        current.append(character)

    parts.append(''.join(current))
    return parts


def rewrite_declarations(body, variables):
    # One rule's declarations, with the variables resolved and what a help
    # viewer cannot lay out left out.  Returns None if nothing is left --
    # which is what becomes of the `:root` block, every declaration in it
    # being a custom property that has just been resolved away.
    kept = []

    for declaration in split_declarations(body):
        if ':' not in declaration:
            continue

        name, _, value = declaration.partition(':')
        name, value = name.strip(), value.strip()

        if not name or name.startswith('--'):
            continue
        if DROPPED_PROPERTY_RE.match(name):
            continue

        value = resolve_value(value, variables).strip()
        if not value:
            continue

        dropped = DROPPED_VALUES.get(name)
        if dropped is not None and dropped.match(value.split()[0]):
            continue

        if name == 'font-size':
            value = relative_font_size(value)

        kept.append('%s: %s' % (name, value))

    return ';\n    '.join(kept) if kept else None


def block_end(css_text, start):
    # The offset just past the `}` that closes the block opening at `start`,
    # counting the blocks nested in it and passing over anything quoted.
    depth = 1
    quote = None
    index = start + 1

    while index < len(css_text) and depth:
        character = css_text[index]
        if quote is not None:
            if character == quote:
                quote = None
        elif character in '"\'':
            quote = character
        elif character == '{':
            depth += 1
        elif character == '}':
            depth -= 1
        index += 1

    return index


def rewrite_rules(css_text, variables):
    # Walks the sheet a brace block at a time.  Writing this out rather than
    # reaching for a CSS parser keeps the output recognisable as the sheet it
    # came from: the selectors, their order and the `@media` they sit in are
    # all passed through as they were written.
    out = []
    index = 0

    while True:
        start = css_text.find('{', index)
        if start < 0:
            out.append(css_text[index:])
            break

        prelude = css_text[index:start]
        end = block_end(css_text, start)
        body = css_text[start + 1:end - 1]
        index = end
        stripped = prelude.strip()

        if stripped.startswith('@media'):
            if keep_media(stripped):
                inner = rewrite_rules(body, variables)
                if inner.strip():
                    out.append('%s{%s}' % (prelude, inner))
        elif stripped.startswith('@'):
            out.append('%s{%s}' % (prelude, body))
        else:
            declarations = rewrite_declarations(body, variables)
            if declarations is not None:
                out.append('%s{\n    %s;\n}' % (prelude, declarations))

    return ''.join(out)


def clean(css_text):
    return IMPORT_RE.sub('', COMMENT_RE.sub('', css_text))


def rules_outside_root(css_text):
    return ROOT_RE.sub('', css_text).strip()


LIGHT_HEADER = '''\
/* The stylesheet of the Qt Help (.qch) rendition of the documentation.
 *
 * It is javadoc's own stylesheet with its custom properties resolved and the
 * layout a help viewer cannot follow left out, plus a layer that fits the
 * result to a help pane.  Generated by "commands/qch_css.py"; edit that, or
 * "qch-viewer.css".
 */
'''

DARK_HEADER = '''\
/* The dark stylesheet of the Qt Help (.qch) rendition of the documentation.
 *
 * Qt Assistant and Qt Creator serve this file in place of "offline.css" or
 * "offline-simple.css" when their own theme is dark.  It is the light
 * stylesheet resolved against a dark palette instead of javadoc's own.
 * Generated by "commands/qch_css.py"; edit that, or "qch-dark.css".
 */
'''


def read_asset(name):
    with open(os.path.join(ASSET_DIR, name), encoding='utf-8') as a_file:
        return a_file.read()


def build_stylesheets(source_css, viewer_css, dark_css):
    # `source_css` is the sheet the pages came with.  The two assets are read
    # for the variables they override -- the viewer's for both sheets, the
    # dark one for the dark sheet alone -- and for the rules they add, which
    # go after everything the source sheet says and therefore win.
    source_css = clean(source_css)
    viewer_css = clean(viewer_css)
    dark_css = clean(dark_css)

    light_variables = read_root_variables(source_css)
    light_variables.update(read_root_variables(viewer_css))

    dark_variables = dict(light_variables)
    dark_variables.update(read_root_variables(dark_css))

    viewer_rules = rules_outside_root(viewer_css)
    dark_rules = rules_outside_root(dark_css)

    light = LIGHT_HEADER + rewrite_rules(source_css, light_variables)
    dark = DARK_HEADER + rewrite_rules(source_css, dark_variables)

    if viewer_rules:
        light += '\n' + section(VIEWER_CSS, viewer_rules, light_variables)
        dark += '\n' + section(VIEWER_CSS, viewer_rules, dark_variables)
    if dark_rules:
        dark += '\n' + section(DARK_CSS, dark_rules, dark_variables)

    return light, dark


def section(title, css_text, variables):
    return '\n/* ---- %s ---- */\n%s\n' % (
        title, rewrite_rules(css_text, variables))


def find_stylesheets(source_root):
    # Where each of the bundle's stylesheets turned out to be, as a path
    # relative to the root of it.  A zone the bundle has no sheet for is left
    # out, and the pages in it fall back to the other one.
    found = {}

    for zone, candidates in CSS_SOURCES.items():
        for rel_path in candidates:
            if os.path.isfile(os.path.join(source_root, rel_path)):
                found[zone] = rel_path
                break

    return found


def write_stylesheets(source_root, dest_root, sheets):
    # Writes our sheets beside each of the sheets the bundle came with, so
    # that a page goes on linking a file in the directory it always linked.
    written = []

    for rel_path in sorted(set(sheets.values())):
        with open(os.path.join(source_root, rel_path),
                  encoding='utf-8') as a_file:
            light, dark = build_stylesheets(
                a_file.read(), read_asset(VIEWER_CSS), read_asset(DARK_CSS))

        directory = os.path.dirname(rel_path)
        target = os.path.join(dest_root, directory)
        os.makedirs(target, exist_ok=True)

        for css_name in LIGHT_CSS_NAMES:
            write_text(os.path.join(target, css_name), light)
        write_text(os.path.join(target, DARK_CSS_NAME), dark)

        written.append(directory)

    return written


def write_text(path, text):
    with open(path, 'w', encoding='utf-8') as a_file:
        a_file.write(text)


def zone_of(rel_path):
    # Which of the bundle's stylesheets a page follows, by where it sits:
    # javadoc's for the API documentation, the shared one for everything
    # else -- the specifications, the manual pages, the legal notices.
    head = rel_path.replace(os.sep, '/').split('/')[0]
    return ZONE_API if head == API_DIR else ZONE_SHARED


def stylesheet_href(rel_path, sheets):
    # The link the page carries, relative to the page itself.
    zone = zone_of(rel_path)
    source = sheets.get(zone) or next(iter(sheets.values()))

    target = os.path.join(os.path.dirname(source), LINKED_CSS_NAME)
    href = os.path.relpath(target, os.path.dirname(rel_path))
    return href.replace(os.sep, '/')
