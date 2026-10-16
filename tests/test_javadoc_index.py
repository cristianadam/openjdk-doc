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

import os
import shutil
import tempfile
import unittest

from commands import javadoc_index

ELEMENT_LIST = '''\
module:java.base
java.lang
java.util

module:java.se
'''

MODULE_INDEX = 'moduleSearchIndex = [{"l":"java.base"},{"l":"java.se"}];'

PACKAGE_INDEX = ('packageSearchIndex = ['
                 '{"l":"All Packages","u":"allpackages-index.html","k":"18"},'
                 '{"m":"java.base","l":"java.lang"},'
                 '{"m":"java.base","l":"java.util"}];')

TYPE_INDEX = ('typeSearchIndex = ['
              '{"p":"java.lang","l":"String"},'
              '{"p":"java.util","l":"Map.Entry","k":"10"},'
              '{"l":"All Classes","u":"allclasses-index.html","k":"18"}];')

MEMBER_INDEX = ('memberSearchIndex = ['
                '{"p":"java.lang","c":"String","l":"length()"},'
                '{"p":"java.lang","c":"String","l":"String(byte[], int)",'
                '"u":"%3Cinit%3E(byte[],int)","k":"3"},'
                '{"p":"java.lang","c":"String","l":"codePointCount(int, int)",'
                '"u":"codePointCount(int,int)"},'
                '{"p":"java.lang","c":"String","l":"CASE_INSENSITIVE_ORDER"},'
                '{"p":"java.util","c":"Map.Entry","l":"getKey()"}];')

SPEC_INDEX = '''<html><body>
<header id="title-block-header"><div class="navbar"><nav><ul>
<li><a href="../api/index.html">API</a></ul></nav></div></header>
<main>
<ul>
  <li><a href="jni/index.html">The JNI Specification</a></li>
  <li><a href="https://example.invalid/jls.html">The Language Spec</a></li>
  <li><a href="jni/index.html">The JNI Specification, again</a></li>
  <li><a href="jvmti.html#intro">JVM Tool Interface</a></li>
</ul>
</main>
<footer class="legal-footer"><a href="../legal/copyright.html">Copyright</a>
</footer>
</body></html>
'''


class ApiTestCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

        self.api_root = os.path.join(self.root, 'api')
        os.makedirs(self.api_root)

        self.write(os.path.join('api', 'element-list'), ELEMENT_LIST)
        self.write(os.path.join('api', 'module-search-index.js'),
                   MODULE_INDEX)
        self.write(os.path.join('api', 'package-search-index.js'),
                   PACKAGE_INDEX)
        self.write(os.path.join('api', 'type-search-index.js'), TYPE_INDEX)
        self.write(os.path.join('api', 'member-search-index.js'),
                   MEMBER_INDEX)

        self.api = javadoc_index.read_api(self.api_root)

    def write(self, rel_path, text):
        path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as a_file:
            a_file.write(text)


class TestReadApi(ApiTestCase):

    def test_reads_the_modules_in_the_order_they_are_listed(self):
        self.assertEqual(['java.base', 'java.se'],
                         [module.name for module in self.api.modules])

    def test_a_module_that_exports_nothing_still_has_a_page(self):
        self.assertEqual('java.se/module-summary.html',
                         self.api.modules[1].url)

    def test_places_each_package_in_its_module(self):
        self.assertEqual(
            [('java.lang', 'java.base'), ('java.util', 'java.base')],
            [(package.name, package.module) for package in self.api.packages])

    def test_the_entries_that_stand_for_a_page_are_left_out(self):
        self.assertEqual(['String', 'Map.Entry'],
                         [a_type.name for a_type in self.api.types])

    def test_works_out_the_page_of_a_type_from_its_package(self):
        self.assertEqual('java.base/java/lang/String.html',
                         self.api.types[0].url)

    def test_a_nested_type_is_a_page_of_its_own(self):
        self.assertEqual('java.base/java/util/Map.Entry.html',
                         self.api.types[1].url)

    def test_a_member_points_into_the_page_of_its_type(self):
        members = {member.name: member.url for member in self.api.members}
        self.assertEqual('java.base/java/lang/String.html#length()',
                         members['length()'])
        self.assertEqual(
            'java.base/java/util/Map.Entry.html#getKey()',
            members['getKey()'])

    def test_encodes_a_signature_the_way_the_page_links_it(self):
        # The index has the angle brackets of `<init>` escaped already and
        # the square ones of `byte[]` not, so encoding what it says as it
        # stands would escape the percent signs along with the rest.
        members = {member.name: member.url for member in self.api.members}
        self.assertEqual(
            'java.base/java/lang/String.html#%3Cinit%3E(byte%5B%5D,int)',
            members['String(byte[], int)'])

    def test_keeps_the_separators_of_a_parameter_list_readable(self):
        members = {member.name: member.url for member in self.api.members}
        self.assertEqual(
            'java.base/java/lang/String.html#codePointCount(int,int)',
            members['codePointCount(int, int)'])

    def test_a_field_needs_no_encoding(self):
        members = {member.name: member.url for member in self.api.members}
        self.assertEqual(
            'java.base/java/lang/String.html#CASE_INSENSITIVE_ORDER',
            members['CASE_INSENSITIVE_ORDER'])


class TestLocalLinks(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.write(os.path.join('specs', 'index.html'), SPEC_INDEX)
        self.links = javadoc_index.local_links(self.root, 'specs/index.html')

    def test_reads_the_pages_the_index_lists(self):
        self.assertEqual(
            [('The JNI Specification', 'specs/jni/index.html'),
             ('JVM Tool Interface', 'specs/jvmti.html')],
            self.links)

    def test_an_index_that_is_not_there_is_no_error(self):
        self.assertEqual([], javadoc_index.local_links(self.root, 'nope.html'))


if __name__ == '__main__':
    unittest.main()
