#!/usr/bin/env python3

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

# Turns the documentation bundle into the tree that goes into the .qch.
#
# Every page is rewritten for a help viewer (see `commands/qch_html.py`), the
# stylesheets are written out light and dark (see `commands/qch_css.py`), and
# the images the pages draw on are carried over as they are.

import argparse
import concurrent.futures
import os
import shutil

from commands import qch_css
from commands import qch_html

# Directories left out of the archive.
#
# The A-Z index is twenty-four megabytes of pages that say what the Index
# pane of the help viewer says, in a worse form; the scripts and the web
# fonts are for a browser, and no help viewer runs or loads either.
SKIPPED_DIRS = [
    os.path.join('api', 'index-files'),
    os.path.join('api', 'script-files'),
    os.path.join('api', 'resource-files', 'fonts'),
]

# Pages left out of it.  The search page is a form and a script; the page at
# the root is a `<meta refresh>` pointing at the API overview, which a help
# viewer shows as an empty window rather than following.
SKIPPED_FILES = [
    os.path.join('api', 'search.html'),
    'index.html',
]

# What is carried over untouched.  The documentation draws on a hundred and
# ninety-odd images between the class diagrams, the Swing component
# illustrations and the arrows of javadoc's own furniture.
ASSET_SUFFIXES = ('.svg', '.png', '.gif', '.jpg', '.jpeg', '.ico', '.webp')


def is_skipped(rel_path):
    if rel_path in SKIPPED_FILES:
        return True
    return any(rel_path == directory or rel_path.startswith(directory + os.sep)
               for directory in SKIPPED_DIRS)


def gather(source_root):
    # The pages to rewrite and the files to copy, as paths relative to the
    # root of the bundle.
    pages = []
    assets = []

    for directory, _, names in os.walk(source_root):
        for name in names:
            rel_path = os.path.relpath(os.path.join(directory, name),
                                       source_root)
            if is_skipped(rel_path):
                continue

            if name.endswith('.html'):
                pages.append(rel_path)
            elif name.lower().endswith(ASSET_SUFFIXES):
                assets.append(rel_path)

    return sorted(pages), sorted(assets)


def copy_assets(source_root, dest_root, assets):
    for rel_path in assets:
        dst_path = os.path.join(dest_root, rel_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copyfile(os.path.join(source_root, rel_path), dst_path)

    return len(assets)


def preprocess_pages(source_root, dest_root, pages, sheets, verbose):
    converted = 0

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(qch_html.preprocess_html_file,
                            os.path.join(source_root, rel_path),
                            os.path.join(dest_root, rel_path),
                            qch_css.stylesheet_href(rel_path, sheets))
            for rel_path in pages
        ]

        for index, future in enumerate(futures):
            if verbose:
                print('Processing page %d/%d: %s' % (
                    index + 1, len(pages), pages[index]))
            converted += future.result()

    return converted


def main():
    parser = argparse.ArgumentParser(prog='preprocess_qch.py')
    parser.add_argument(
        '--src', required=True,
        help='the unpacked documentation bundle, normally "reference/docs"')
    parser.add_argument(
        '--dst', required=True,
        help='where to put the Qt Help rendition of it')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    source_root = args.src
    dest_root = args.dst

    if not os.path.isdir(source_root):
        raise SystemExit(
            '%s is not there; run "make source" to fetch the documentation'
            % source_root)

    # Start from nothing.  The help project takes whatever is left in here as
    # its list of files, so anything an earlier run wrote and this one does
    # not would be shipped inside the .qch -- and a run that failed half way
    # would leave a directory that make takes for finished work.
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)
    os.makedirs(dest_root)

    sheets = qch_css.find_stylesheets(source_root)
    if not sheets:
        raise SystemExit('%s carries no stylesheet the pages could link'
                         % source_root)

    pages, assets = gather(source_root)

    converted = preprocess_pages(source_root, dest_root, pages, sheets,
                                 args.verbose)
    print('Rewrote %d pages, rebuilding %d summary tables'
          % (len(pages), converted))

    print('Copied %d images' % copy_assets(source_root, dest_root, assets))

    written = qch_css.write_stylesheets(source_root, dest_root, sheets)
    print('Wrote %d stylesheets in %s'
          % (len(written) * (len(qch_css.LIGHT_CSS_NAMES) + 1),
             ', '.join(written)))


if __name__ == '__main__':
    main()
