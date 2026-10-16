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

import unittest

from commands import javadoc_index
from commands import qhp

API = javadoc_index.Api(
    modules=[javadoc_index.Module('java.base',
                                  'java.base/module-summary.html')],
    packages=[javadoc_index.Package(
        'java.lang', 'java.base',
        'java.base/java/lang/package-summary.html')],
    types=[
        javadoc_index.Type('String', 'java.lang', 'java.base',
                           'java.base/java/lang/String.html'),
        javadoc_index.Type('Gone', 'java.lang', 'java.base',
                           'java.base/java/lang/Gone.html'),
    ],
    members=[
        javadoc_index.Member('charAt(int)', 'String', 'java.lang',
                             'java.base',
                             'java.base/java/lang/String.html#charAt(int)'),
        javadoc_index.Member('vanished()', 'Gone', 'java.lang', 'java.base',
                             'java.base/java/lang/Gone.html#vanished()'),
    ])

FILES = [
    'api/index.html',
    'api/allpackages-index.html',
    'api/allclasses-index.html',
    'api/java.base/module-summary.html',
    'api/java.base/java/lang/package-summary.html',
    'api/java.base/java/lang/String.html',
    'api/resource-files/offline-simple.css',
]


class TestBuildProject(unittest.TestCase):

    def setUp(self):
        self.root = qhp.build_project(
            API, 'reference/docs', FILES, 'Java SE 25 & JDK 25',
            'org.openjdk.javase.25', 'javase25', ['java', '25'])

    def sections(self):
        return {element.get('title'): element.get('ref')
                for element in self.root.iter('section')}

    def keywords(self):
        return {element.get('name'): element.get('ref')
                for element in self.root.iter('keyword')}

    def test_names_the_help_namespace_and_the_virtual_folder(self):
        self.assertEqual('org.openjdk.javase.25',
                         self.root.findtext('namespace'))
        self.assertEqual('javase25', self.root.findtext('virtualFolder'))

    def test_states_the_filter_attributes_twice_over(self):
        self.assertEqual(
            ['java', '25'],
            [element.text
             for element in self.root.findall('customFilter/'
                                              'filterAttribute')])
        self.assertEqual(
            ['java', '25'],
            [element.text
             for element in self.root.findall('filterSection/'
                                              'filterAttribute')])

    def test_the_contents_follow_the_shape_of_the_api(self):
        sections = self.sections()
        self.assertEqual('api/java.base/module-summary.html',
                         sections['java.base'])
        self.assertEqual('api/java.base/java/lang/package-summary.html',
                         sections['java.lang'])
        self.assertEqual('api/java.base/java/lang/String.html',
                         sections['String'])

    def test_the_contents_stop_at_the_types(self):
        self.assertNotIn('charAt(int)', self.sections())

    def test_a_type_is_indexed_under_both_of_its_names(self):
        keywords = self.keywords()
        self.assertEqual('api/java.base/java/lang/String.html',
                         keywords['String'])
        self.assertEqual('api/java.base/java/lang/String.html',
                         keywords['java.lang.String'])

    def test_only_one_of_the_two_carries_the_identifier(self):
        # qhelpgenerator keys the index on the identifier alone and keeps the
        # first keyword it sees for each one, so giving both of them the same
        # identifier would drop the second rather than record the type under
        # both of its names.
        both = ('String', 'java.lang.String')
        identifiers = [element.get('id')
                       for element in self.root.iter('keyword')
                       if element.get('name') in both]
        self.assertEqual(['java.lang.String', None], identifiers)

    def test_a_member_is_indexed_under_the_type_it_belongs_to(self):
        self.assertEqual('api/java.base/java/lang/String.html#charAt(int)',
                         self.keywords()['String.charAt(int)'])

    def test_a_member_is_identified_by_its_qualified_name(self):
        identifiers = {element.get('name'): element.get('id')
                       for element in self.root.iter('keyword')}
        self.assertEqual('java.lang.String.charAt(int)',
                         identifiers['String.charAt(int)'])

    def test_a_reference_into_a_page_that_is_not_carried_is_left_out(self):
        self.assertNotIn('Gone', self.sections())
        self.assertNotIn('Gone.vanished()', self.keywords())

    def test_the_files_are_the_ones_it_was_given(self):
        self.assertEqual(
            FILES, [element.text for element in self.root.iter('file')])


if __name__ == '__main__':
    unittest.main()
