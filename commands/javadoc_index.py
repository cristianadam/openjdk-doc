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

# Reads the indexes javadoc writes beside the pages it generates.
#
# A .qch needs a table of contents and a keyword index, and both are already
# in the documentation: javadoc writes the lists its own search box works
# from -- the modules, the packages, every type and every member -- as four
# JavaScript files holding nothing but a JSON array.  Reading those is a good
# deal more reliable than parsing ten thousand pages back out, and it is what
# the search box itself goes by, so what we build points where javadoc means
# each name to point.
#
# No URL is spelled out in them, except for the handful of entries that stand
# for a page rather than an element.  The rest is worked out the way
# `script-files/search.js` does it, from the module a package belongs to and
# the package a type belongs to; see `type_url` and `member_url`.

import json
import os
import re

from collections import namedtuple
from urllib.parse import quote, unquote

from lxml import html

# Where the API documentation sits inside the unpacked doc bundle.
API_DIR = 'api'

# The file each index is written to, and the name of the variable it assigns
# to -- which is all that stands between us and plain JSON.
SEARCH_INDEXES = {
    'module': 'module-search-index.js',
    'package': 'package-search-index.js',
    'type': 'type-search-index.js',
    'member': 'member-search-index.js',
}

Module = namedtuple('Module', 'name url')
Package = namedtuple('Package', 'name module url')
Type = namedtuple('Type', 'name package module url')
Member = namedtuple('Member', 'name owner package module url')

Api = namedtuple('Api', 'modules packages types members')


def read_search_index(api_root, kind):
    # The file is `<name>SearchIndex = [ ... ];`, so the array is everything
    # between the first bracket and the last.  json.loads is handed only that
    # much rather than the file being treated as JavaScript.
    path = os.path.join(api_root, SEARCH_INDEXES[kind])
    with open(path, encoding='utf-8') as a_file:
        text = a_file.read()

    start = text.index('[')
    end = text.rindex(']')
    return json.loads(text[start:end + 1])


def read_element_list(api_root):
    # `element-list` is the file javadoc writes for `-link` to read: a run of
    # package names under each `module:<name>` line.  We use it for the order
    # the modules and packages are listed in, which is the alphabetical one
    # the generated pages follow, and as the answer for a module that exports
    # no package of its own -- `java.se` is one -- since those appear in no
    # search index but have a summary page all the same.
    path = os.path.join(api_root, 'element-list')
    modules = []
    packages = {}
    current = None

    with open(path, encoding='utf-8') as a_file:
        for line in a_file:
            line = line.strip()
            if not line:
                continue
            if line.startswith('module:'):
                current = line[len('module:'):]
                modules.append(current)
                packages[current] = []
            elif current is not None:
                packages[current].append(line)

    return modules, packages


# What javadoc leaves alone when it turns a member's signature into the
# fragment of a URL.  Everything outside the unreserved set is percent-encoded
# -- `<init>` becomes `%3Cinit%3E` and `byte[]` becomes `byte%5B%5D` -- while
# the parentheses and the commas of the parameter list are kept readable.
FRAGMENT_SAFE = '(),'


def encode_fragment(fragment):
    # The index is half-encoded already: a constructor is written
    # `%3Cinit%3E(byte[])`, with the angle brackets escaped and the square
    # ones not.  Encoding that as it stands would escape the percent signs
    # and point at an anchor no page has, so it is decoded first and then
    # encoded the whole way -- which is what the page itself links.
    return quote(unquote(fragment), safe=FRAGMENT_SAFE)


def package_path(name):
    return name.replace('.', '/')


def module_url(module):
    return '%s/module-summary.html' % module


def package_url(module, package):
    return '%s/%s/package-summary.html' % (module, package_path(package))


def type_url(module, package, name):
    # A nested type is named `Outer.Inner` here and written to a file of that
    # name, so this holds for those as well.
    return '%s/%s/%s.html' % (module, package_path(package), name)


def member_url(module, package, owner, fragment):
    return '%s#%s' % (type_url(module, package, owner),
                      encode_fragment(fragment))


def read_api(api_root):
    # The four indexes and `element-list`, resolved against each other into
    # the elements of the API and the page each one is documented on.
    module_names, module_packages = read_element_list(api_root)

    # A package names the module it belongs to in its own index entry, and
    # nothing else does, so this is what lets a type or a member be placed.
    package_module = {}
    for entry in read_search_index(api_root, 'package'):
        # The index opens with an entry for the "All Packages" page, which
        # names no module because it stands for a page rather than a package.
        if 'm' in entry:
            package_module[entry['l']] = entry['m']

    for module, names in module_packages.items():
        for name in names:
            package_module.setdefault(name, module)

    modules = [Module(name, module_url(name)) for name in module_names]

    packages = []
    for module in module_names:
        for name in sorted(module_packages[module]):
            packages.append(Package(name, module, package_url(module, name)))

    types = []
    for entry in read_search_index(api_root, 'type'):
        package = entry.get('p')
        module = package_module.get(package)
        if module is None:
            # An entry standing for a page -- "All Classes and Interfaces" --
            # or a type in a package the bundle does not document.
            continue
        types.append(Type(entry['l'], package, module,
                          type_url(module, package, entry['l'])))

    members = []
    for entry in read_search_index(api_root, 'member'):
        package = entry.get('p')
        module = package_module.get(package)
        if module is None:
            continue
        owner = entry['c']
        # `u` is only written when the fragment differs from the label, which
        # it does for anything taking parameters: the label shortens the
        # parameter types and the fragment spells them out.
        fragment = entry.get('u', entry['l'])
        members.append(Member(entry['l'], owner, package, module,
                              member_url(module, package, owner, fragment)))

    return Api(modules, packages, types, members)


# -- the pages that stand on their own -------------------------------------

# The pages of the API documentation that document no element: the overviews
# and the generated lists.  Spelled out rather than discovered, because the
# order and the wording are the ones the navigation bar used, and because the
# ones we leave out -- the A-Z index, which the Index pane of the help viewer
# replaces, and the search page, which needs the JavaScript -- are left out
# of the archive too.
OVERVIEW_PAGES = [
    ('All Modules', 'index.html'),
    ('All Packages', 'allpackages-index.html'),
    ('All Classes and Interfaces', 'allclasses-index.html'),
    ('Class Hierarchy', 'overview-tree.html'),
]

LIST_PAGES = [
    ('Constant Field Values', 'constant-values.html'),
    ('Deprecated API', 'deprecated-list.html'),
    ('New API', 'new-list.html'),
    ('Preview API', 'preview-list.html'),
    ('Restricted Methods', 'restricted-list.html'),
    ('Serialized Form', 'serialized-form.html'),
    ('System Properties', 'system-properties.html'),
    ('External Specifications', 'external-specs.html'),
    ('Search Tags', 'search-tags.html'),
    ('How This API Document Is Organized', 'help-doc.html'),
]


# -- the specifications and the tool guides --------------------------------

# The doc bundle carries a good deal besides the API: the JNI and JVM TI
# specifications, the serialization and RMI specifications, and a manual page
# for every tool in the JDK.  They are a handful of pages each and they are
# linked from one index apiece, so the contents are taken from those indexes
# rather than listed here -- a release that adds a specification picks it up
# on its own.

SPEC_INDEXES = [
    ('Specifications', 'specs/index.html'),
    ('Tool Guides', 'specs/man/index.html'),
]

SPACE_RE = re.compile(r'\s+')


def local_links(docs_root, index_path):
    # The pages one of those indexes links to, in the order it links them,
    # each with the text it is linked under.
    #
    # Only the body of the index counts.  What surrounds it is the navigation
    # bar the page shares with every other one -- "API", "TOOL GUIDES" -- and
    # the copyright notice at the foot, none of which is a specification.
    # Only local pages count as well: the index points at the language and
    # virtual machine specifications too, and those are published on the web
    # rather than carried in the bundle.
    path = os.path.join(docs_root, index_path)
    if not os.path.isfile(path):
        return []

    with open(path, encoding='utf-8') as a_file:
        document = html.document_fromstring(a_file.read())

    body = document.find('.//main')
    if body is None:
        body = document.find('body')
    if body is None:
        return []

    directory = os.path.dirname(index_path)
    seen = set()
    links = []

    for anchor in body.iter('a'):
        href = (anchor.get('href') or '').partition('#')[0]
        if not href.endswith('.html') or '://' in href:
            continue

        target = os.path.normpath(os.path.join(directory, href))
        if target.startswith(os.pardir) or target in seen:
            # A link back out to the API documentation, or the page saying
            # again what it already said further up.
            continue

        label = SPACE_RE.sub(' ', anchor.text_content()).strip()
        if not label:
            continue

        seen.add(target)
        links.append((label, target.replace(os.sep, '/')))

    return links
