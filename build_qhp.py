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

# Writes the help project for the tree `preprocess_qch.py` built.
#
# The contents and the index come out of the bundle rather than out of the
# tree: javadoc writes the lists of every module, package, type and member it
# documented, and reading those is both quicker and more faithful than
# parsing ten thousand pages back out.  See `commands/javadoc_index.py`.

import argparse
import os

from commands import javadoc_index
from commands import qhp


def main():
    parser = argparse.ArgumentParser(prog='build_qhp.py')
    parser.add_argument(
        '--docs', required=True,
        help='the unpacked documentation bundle, normally "reference/docs"')
    parser.add_argument(
        '--src', required=True,
        help='the Qt Help rendition of it, whose files go in the project')
    parser.add_argument('--dst', required=True,
                        help='the help project to write')
    parser.add_argument('--title', required=True,
                        help='what the documentation is called')
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--virtual-folder', required=True)
    parser.add_argument(
        '--filter-attribute', action='append', default=[],
        help='may be given more than once')
    args = parser.parse_args()

    api_root = os.path.join(args.docs, javadoc_index.API_DIR)
    if not os.path.isdir(api_root):
        raise SystemExit('%s is not there; run "make source"' % api_root)

    api = javadoc_index.read_api(api_root)
    print('The bundle documents %d modules, %d packages, %d types and '
          '%d members' % (len(api.modules), len(api.packages),
                          len(api.types), len(api.members)))

    files = qhp.list_files(args.src)

    root = qhp.build_project(api, args.docs, files, args.title,
                             args.namespace, args.virtual_folder,
                             args.filter_attribute)

    os.makedirs(os.path.dirname(os.path.abspath(args.dst)), exist_ok=True)
    qhp.write_project(args.dst, root)

    print('Wrote %s: %d files, %d contents entries, %d keywords'
          % (args.dst, len(files), qhp.count(root, 'section'),
             qhp.count(root, 'keyword')))


if __name__ == '__main__':
    main()
