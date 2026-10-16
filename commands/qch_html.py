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

# Turns one generated page into the rendition that goes into the .qch.
#
# The help viewers that read the archive -- Qt Assistant since Qt 6.2 and Qt
# Creator since 4.11 -- render with litehtml, which is a browser engine as
# far as the cascade and the box model go but runs no JavaScript and lays out
# no CSS grid.  Two things follow, and they are most of what this file does.
#
# Nothing that needs a script is worth carrying: the search box, the filter
# over the contents of a page, the buttons that switch a method table between
# "static" and "instance", the button that copies a link.  Each is dropped,
# and the page is left with the navigation the help viewer provides anyway --
# its own table of contents, its own index, its own search.
#
# What does have to be rebuilt is the summary tables.  Every list of fields,
# constructors and methods on a class page is a flat run of `<div>`s laid out
# by `grid-template-columns`, and read without grid that is one cell per
# line: a method, then its description, then the next method.  They are the
# bulk of a class page.  So the run is folded back into the `<table>` it
# stands for -- the column count is in the class name, `three-column-summary`
# and the rest -- which litehtml lays out as the page means it.

import os
import re

from lxml import etree, html

# `<N>-column-summary` says how wide a summary table is; the search results
# page spells the same thing `<N>-column-search-results`.
COLUMN_COUNTS = {'one': 1, 'two': 2, 'three': 3, 'four': 4,
                 'five': 5, 'six': 6}

COLUMN_RE = re.compile(
    r'\b(%s)-column(?:-release)?-(?:summary|search-results)\b'
    % '|'.join(COLUMN_COUNTS))

# Everything a script would have driven, by class name.
SCRIPTED_CLASSES = [
    'top-nav',          # the navigation bar, and the search box in it
    'sub-nav',          # the breadcrumb, which is lifted out of it first
    'nav-list-search',
    'skip-nav',
    'table-tabs',       # the buttons that filter a method table
    'navbar',           # what the manual pages have in place of a navbar
]

# The in-page table of contents, which the Contents pane of the help viewer
# says again and lays out better.
SCRIPTED_NAV_CLASSES = ['toc']

# Elements that carry no text of their own and stand for something only a
# script could do.
SCRIPTED_TAGS = ['script', 'noscript', 'button', 'input', 'form']

# Of those, the ones that stand in the middle of a line, whose tail is the
# space before the next word rather than the newline after a block.
INLINE_TAGS = frozenset(['button', 'input'])

# `<style>` appears on the manual pages, where pandoc writes a block of
# boilerplate for features none of them use; `qch-viewer.css` says what is
# worth keeping of it.  `<link>` and `<meta>` are rewritten rather than kept:
# the page links the stylesheet we generate, and the `keywords` meta tags --
# sixty of them on a class page -- are a search engine's business.
HEAD_TAGS = ['script', 'style', 'link', 'meta']

DOCTYPE = '<!DOCTYPE html>'


def classes_of(element):
    return (element.get('class') or '').split()


def by_class(root, name, tag='*'):
    return root.xpath(
        './/%s[contains(concat(" ", normalize-space(@class), " "), " %s ")]'
        % (tag, name))


def drop(element, keep_tail=True):
    # Removes an element.  The text that followed it is kept where it was,
    # since in running text that is the space between two words -- unless the
    # element stood on a line of its own, where keeping it would leave a
    # blank line behind for every one of the sixty `<meta>` tags a class page
    # carries.
    parent = element.getparent()
    if parent is None:
        return

    if keep_tail and element.tail:
        previous = element.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or '') + element.tail
        else:
            parent.text = (parent.text or '') + element.tail

    parent.remove(element)


def unwrap(element):
    # Replaces an element with what it holds.
    parent = element.getparent()
    if parent is None:
        return

    index = parent.index(element)
    children = list(element)

    def append_text(text):
        if not text:
            return
        if index == 0:
            parent.text = (parent.text or '') + text
        else:
            before = parent[index - 1]
            before.tail = (before.tail or '') + text

    append_text(element.text)

    for offset, child in enumerate(children):
        parent.insert(index + offset, child)

    if element.tail:
        if children:
            children[-1].tail = (children[-1].tail or '') + element.tail
        else:
            append_text(element.tail)

    parent.remove(element)


# -- the head --------------------------------------------------------------

def rewrite_head(document, css_href):
    head = document.find('head')
    if head is None:
        head = etree.SubElement(document, 'head')
        document.insert(0, head)

    for tag in HEAD_TAGS:
        for element in head.findall(tag):
            drop(element, keep_tail=False)

    charset = etree.Element('meta')
    charset.set('charset', 'utf-8')
    head.insert(0, charset)

    link = etree.SubElement(head, 'link')
    link.set('rel', 'stylesheet')
    link.set('type', 'text/css')
    link.set('href', css_href)


# -- the body --------------------------------------------------------------

def take_breadcrumb(document):
    # The breadcrumb -- `java.base`, `java.lang`, `String` -- sits in the
    # navigation bar, which goes.  It is the one part of it worth keeping:
    # the Contents pane says where a page sits only while it is the page the
    # reader arrived at from there, and a page reached from a link says
    # nothing at all otherwise.
    for element in by_class(document, 'sub-nav-list', 'ol'):
        drop(element)
        return element
    return None


def is_empty(element):
    if element.text and element.text.strip():
        return False
    return all(is_empty(child) and not (child.tail and child.tail.strip())
               for child in element)


def strip_scripted(document):
    # The comments mark out the navigation bars and the class data, which is
    # a kindness to anyone reading the generated source and no use to a
    # reader of the page.
    for comment in list(document.iter(etree.Comment)):
        drop(comment, keep_tail=False)

    for tag in SCRIPTED_TAGS:
        for element in list(document.iter(tag)):
            drop(element, keep_tail=tag in INLINE_TAGS)

    for name in SCRIPTED_CLASSES:
        for element in by_class(document, name):
            drop(element, keep_tail=False)

    for name in SCRIPTED_NAV_CLASSES:
        for element in by_class(document, name, 'nav'):
            drop(element, keep_tail=False)

    # What is left of the banner once the navigation bars are out of it is an
    # empty `<nav>` in an empty `<header>` -- except on the manual pages,
    # where the header holds the title of the page.
    for tag in ('nav', 'header'):
        for element in list(document.iter(tag)):
            if is_empty(element):
                drop(element, keep_tail=False)

    # The sidebar and the content were laid out side by side with grid, and
    # there is no sidebar any more.
    for element in by_class(document, 'main-grid'):
        unwrap(element)

    # A line-break opportunity, which litehtml does not take; libxml2 reads
    # it as an element with content rather than an empty one, so leaving it
    # in would wrap the rest of a signature inside it.
    for element in list(document.iter('wbr')):
        unwrap(element)


def place_breadcrumb(document, breadcrumb):
    if breadcrumb is None:
        return

    main = document.find('.//main')
    if main is None:
        body = document.find('body')
        if body is None:
            return
        body.insert(0, breadcrumb)
    else:
        main.insert(0, breadcrumb)


# -- the summary tables ----------------------------------------------------

def column_count(element):
    match = COLUMN_RE.search(element.get('class') or '')
    return COLUMN_COUNTS[match.group(1)] if match else None


def convert_summary_table(element):
    # The cells are the direct children, in reading order, the first row of
    # them being the headers.  Nothing else is in there, so the rows follow
    # from the column count alone.
    columns = column_count(element)
    if columns is None or len(element) == 0:
        return False

    cells = list(element)
    headers = [cell for cell in cells[:columns]
               if 'table-header' in classes_of(cell)]

    table = etree.Element('table')
    table.set('class', ' '.join(
        [name for name in classes_of(element) if not COLUMN_RE.match(name)]))
    table.tail = element.tail

    if headers:
        row = etree.SubElement(etree.SubElement(table, 'thead'), 'tr')
        for cell in headers:
            retag(cell, 'th')
            row.append(cell)
        cells = cells[len(headers):]

    body = etree.SubElement(table, 'tbody')
    row = None

    for index, cell in enumerate(cells):
        if index % columns == 0:
            row = etree.SubElement(body, 'tr')
        retag(cell, 'td')
        row.append(cell)

    element.getparent().replace(element, table)
    return True


# The classes naming the tab a row belongs to, which were there for the
# filter buttons.  The `col-*` ones stay: they are what sets a member name in
# bold and a summary cell in the code font.
TAB_CLASS_RE = re.compile(r'(^|-)summary-table(-tab\d+)?$')


def retag(cell, tag):
    cell.tag = tag
    # The text between the cells is the newline javadoc writes after each of
    # them, and a newline between two `<td>`s is a space in the rendered row.
    cell.tail = None

    kept = [name for name in classes_of(cell)
            if not TAB_CLASS_RE.search(name)]

    if kept:
        cell.set('class', ' '.join(kept))
    elif 'class' in cell.attrib:
        del cell.attrib['class']


def convert_summary_tables(document):
    converted = 0
    for name in ('summary-table', 'details-table'):
        for element in by_class(document, name, 'div'):
            if convert_summary_table(element):
                converted += 1
    return converted


# -- the page --------------------------------------------------------------

def preprocess_html(text, css_href):
    document = html.document_fromstring(text)

    rewrite_head(document, css_href)
    breadcrumb = take_breadcrumb(document)
    strip_scripted(document)
    place_breadcrumb(document, breadcrumb)
    converted = convert_summary_tables(document)

    return DOCTYPE + '\n' + html.tostring(
        document, encoding='unicode', method='html'), converted


def preprocess_html_file(src_path, dst_path, css_href):
    with open(src_path, encoding='utf-8', errors='replace') as a_file:
        text = a_file.read()

    page, converted = preprocess_html(text, css_href)

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8') as a_file:
        a_file.write(page)

    return converted
