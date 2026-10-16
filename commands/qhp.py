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

# Writes the help project `qhelpgenerator` turns into the .qch.
#
# Three things go in it.  The table of contents is the shape of the API --
# the modules, the packages each one exports and the types in each package --
# which is what the Contents pane of a help viewer shows.  The keywords are
# every element the documentation has a name for, which is what its Index
# pane lists and what it looks a name up in.  The files are everything the
# archive is to carry.
#
# The contents stop at the types.  A branch per member would be another
# fifty thousand entries in a pane that is meant to be read down, and every
# one of them is in the index already, where looking a name up is what the
# pane is for.

import os

from lxml import etree

from commands import javadoc_index

# Where the API documentation sits under the root of the archive; everything
# the index module works out is relative to it.
API_PREFIX = javadoc_index.API_DIR + '/'


def api_ref(url):
    return API_PREFIX + url


def section(parent, title, ref):
    element = etree.SubElement(parent, 'section')
    element.set('title', title)
    element.set('ref', ref)
    return element


def keyword(parent, name, ref, identifier=None):
    element = etree.SubElement(parent, 'keyword')
    element.set('name', name)
    if identifier is not None:
        element.set('id', identifier)
    element.set('ref', ref)


# -- the table of contents -------------------------------------------------

def build_toc(api, docs_root, title, keep):
    toc = etree.Element('toc')
    top = section(toc, title, api_ref('index.html'))

    modules = section(top, 'Modules', api_ref('index.html'))
    build_api_toc(modules, api, keep)

    lists = section(top, 'Lists and Indexes',
                    api_ref('allpackages-index.html'))
    for label, page in (javadoc_index.OVERVIEW_PAGES
                        + javadoc_index.LIST_PAGES):
        if keep(api_ref(page)):
            section(lists, label, api_ref(page))

    # A specification index opens by pointing at the API documentation and at
    # the other index, both of which are branches of their own here.
    elsewhere = {api_ref('index.html')}
    elsewhere.update(index for _, index in javadoc_index.SPEC_INDEXES)

    for label, index in javadoc_index.SPEC_INDEXES:
        if not keep(index):
            continue
        branch = section(top, label, index)
        for page_label, page in javadoc_index.local_links(docs_root, index):
            if keep(page) and page not in elsewhere:
                section(branch, page_label, page)

    return toc


def build_api_toc(parent, api, keep):
    # The packages of a module and the types of a package, gathered once so
    # that the tree can be walked in the order the modules are listed in.
    packages_of = {}
    for package in api.packages:
        packages_of.setdefault(package.module, []).append(package)

    types_of = {}
    for a_type in api.types:
        types_of.setdefault(a_type.package, []).append(a_type)

    for module in api.modules:
        if not keep(api_ref(module.url)):
            continue

        branch = section(parent, module.name, api_ref(module.url))

        for package in packages_of.get(module.name, []):
            if not keep(api_ref(package.url)):
                continue

            leaf = section(branch, package.name, api_ref(package.url))

            for a_type in sorted(types_of.get(package.name, []),
                                 key=lambda item: item.name):
                if keep(api_ref(a_type.url)):
                    section(leaf, a_type.name, api_ref(a_type.url))


# -- the keywords ----------------------------------------------------------

def build_keywords(api, keep):
    keywords = etree.Element('keywords')

    for module in api.modules:
        if keep(api_ref(module.url)):
            keyword(keywords, module.name, api_ref(module.url))

    for package in api.packages:
        if keep(api_ref(package.url)):
            keyword(keywords, package.name, api_ref(package.url))

    for a_type in api.types:
        ref = api_ref(a_type.url)
        if not keep(ref):
            continue
        qualified = '%s.%s' % (a_type.package, a_type.name)
        # Twice over: the simple name is what a reader types, and what the
        # help viewer looks up when F1 is pressed on the word under the
        # cursor; the qualified one is what tells two classes of the same
        # name apart -- there is a `List` in `java.util` and another in
        # `java.awt` -- and what answers to a lookup by identifier.
        #
        # Only the first of them may carry the identifier.  qhelpgenerator
        # keys the index on the identifier alone and keeps the first keyword
        # it sees for each one, so stating it twice would drop the second
        # keyword rather than record it under both names.
        keyword(keywords, a_type.name, ref, qualified)
        keyword(keywords, qualified, ref)

    for member in api.members:
        ref = api_ref(member.url)
        if keep(ref):
            keyword(keywords, '%s.%s' % (member.owner, member.name), ref,
                    '%s.%s.%s' % (member.package, member.owner, member.name))

    return keywords


# -- the files -------------------------------------------------------------

def build_files(files):
    element = etree.Element('files')
    for path in files:
        child = etree.SubElement(element, 'file')
        child.text = path
    return element


# -- the project -----------------------------------------------------------

def build_project(api, docs_root, files, title, namespace, virtual_folder,
                  filter_attributes):
    # A reference into a page the archive does not carry is one the help
    # viewer answers with an empty window, so every one of them is checked
    # against what is actually going in.
    available = frozenset(files)

    def keep(ref):
        return ref.partition('#')[0] in available

    root = etree.Element('QtHelpProject')
    root.set('version', '1.0')

    etree.SubElement(root, 'namespace').text = namespace
    etree.SubElement(root, 'virtualFolder').text = virtual_folder

    custom = etree.SubElement(root, 'customFilter')
    custom.set('name', title)
    for attribute in filter_attributes:
        etree.SubElement(custom, 'filterAttribute').text = attribute

    section_element = etree.SubElement(root, 'filterSection')
    for attribute in filter_attributes:
        etree.SubElement(section_element, 'filterAttribute').text = attribute

    section_element.append(build_toc(api, docs_root, title, keep))
    section_element.append(build_keywords(api, keep))
    section_element.append(build_files(files))

    return root


def write_project(path, root):
    with open(path, 'wb') as a_file:
        a_file.write(etree.tostring(root, encoding='utf-8',
                                    xml_declaration=True, pretty_print=True))


def count(root, tag):
    return len(root.findall('.//' + tag))


def list_files(dest_root):
    # Everything the preprocessing pass left behind, as the help project
    # spells a path: relative to the directory the project file sits in, with
    # forward slashes.
    paths = []

    for directory, _, names in os.walk(dest_root):
        for name in names:
            path = os.path.relpath(os.path.join(directory, name), dest_root)
            paths.append(path.replace(os.sep, '/'))

    return sorted(paths)
