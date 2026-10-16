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
import unittest

from commands import qch_css

SOURCE = '''
@import url('fonts/dejavu.css');

/* the palette */
:root {
    --body-text-color: #181818;
    --body-background-color: #ffffff;
    --section-background-color: var(--body-background-color);
    --body-font-size: 14.2px;
    --link-color: #437291;
}

body {
    color: var(--body-text-color);
    background-color: var(--body-background-color);
    font-size: var(--body-font-size);
}

section {
    background-color: var(--section-background-color);
    border: 1px solid var(--border-color, #e6e6e6);
}

a:link {
    color: var(--link-color);
}

.summary-table {
    display: grid;
    grid-template-columns: minmax(15%, max-content) minmax(20%, auto);
    border: 1px solid #cccccc;
}

.top-nav {
    position: sticky;
    top: 0;
}

.sort-arrow::after {
    background-image: url('data:image/svg+xml; utf8, <svg x="1"/>');
    width: 9px;
}

kbd {
    font-size: 10px;
}

@media screen and (max-width: 800px) {
    .summary-table {
        grid-template-columns: 1fr;
    }
    body {
        color: #000000;
    }
}

@media print {
    body {
        color: #000000;
    }
}
'''

VIEWER = '''
:root {
    --body-font-size: 1em;
}

main {
    display: block;
}
'''

DARK = '''
:root {
    --body-text-color: #d0d0d0;
    --body-background-color: #262626;
}

hr {
    border-color: #4a4a4a;
}
'''


class TestBuildStylesheets(unittest.TestCase):

    def setUp(self):
        self.light, self.dark = qch_css.build_stylesheets(
            SOURCE, VIEWER, DARK)

    def test_resolves_every_variable(self):
        self.assertNotIn('var(', self.light)
        self.assertNotIn('var(', self.dark)

    def test_the_light_sheet_keeps_javadocs_colors(self):
        self.assertIn('color: #181818', self.light)
        self.assertIn('background-color: #ffffff', self.light)

    def test_the_dark_sheet_carries_the_dark_palette(self):
        self.assertIn('color: #d0d0d0', self.dark)
        self.assertIn('background-color: #262626', self.dark)
        self.assertNotIn('#181818', self.dark)

    def test_a_variable_defined_as_another_follows_it(self):
        self.assertIn('background-color: #ffffff', self.light)
        self.assertIn('background-color: #262626', self.dark)

    def test_an_undeclared_variable_falls_back(self):
        self.assertIn('border: 1px solid #e6e6e6', self.light)

    def test_the_root_block_itself_is_gone(self):
        self.assertNotIn(':root', self.light)
        self.assertNotIn('--body-text-color', self.light)

    def test_drops_the_layout_a_help_viewer_cannot_follow(self):
        self.assertNotIn('display: grid', self.light)
        self.assertNotIn('grid-template-columns', self.light)
        self.assertNotIn('position: sticky', self.light)

    def test_keeps_what_the_dropped_rule_said_besides(self):
        self.assertIn('border: 1px solid #cccccc', self.light)

    def test_drops_the_responsive_rules_and_keeps_the_print_ones(self):
        self.assertNotIn('max-width', self.light)
        self.assertIn('@media print', self.light)

    def test_drops_the_font_the_pages_cannot_load(self):
        self.assertNotIn('@import', self.light)

    def test_states_the_sizes_as_proportions_of_the_readers_font(self):
        self.assertIn('font-size: 1em', self.light)
        self.assertIn('font-size: 0.7042em', self.light)

    def test_passes_over_a_semicolon_inside_a_data_url(self):
        self.assertIn("url('data:image/svg+xml; utf8, <svg x=\"1\"/>')",
                      self.light)
        self.assertIn('width: 9px', self.light)

    def test_appends_what_the_assets_add(self):
        self.assertIn('display: block', self.light)
        self.assertIn('border-color: #4a4a4a', self.dark)
        self.assertNotIn('border-color: #4a4a4a', self.light)


class TestResolveValue(unittest.TestCase):

    def test_a_cycle_gives_up_rather_than_running_away(self):
        variables = {'--a': 'var(--b)', '--b': 'var(--a)'}
        self.assertIn('var(', qch_css.resolve_value('var(--a)', variables))

    def test_a_variable_with_neither_value_nor_fallback_is_nothing(self):
        self.assertEqual('', qch_css.resolve_value('var(--missing)', {}))


SHEETS = {
    qch_css.ZONE_API: os.path.join('api', 'resource-files', 'stylesheet.css'),
    qch_css.ZONE_SHARED: os.path.join('resources', 'jdk-default.css'),
}

OLD_SHEETS = {
    qch_css.ZONE_API: os.path.join('api', 'stylesheet.css'),
}


class TestStylesheetHref(unittest.TestCase):

    def test_a_class_page_reaches_javadocs_stylesheet(self):
        self.assertEqual(
            '../../../resource-files/offline-simple.css',
            qch_css.stylesheet_href(
                os.path.join('api', 'java.base', 'java', 'lang',
                             'String.html'), SHEETS))

    def test_a_manual_page_reaches_the_shared_one(self):
        self.assertEqual(
            '../../resources/offline-simple.css',
            qch_css.stylesheet_href(
                os.path.join('specs', 'man', 'java.html'), SHEETS))

    def test_follows_the_stylesheet_to_where_an_older_bundle_keeps_it(self):
        self.assertEqual(
            '../../../offline-simple.css',
            qch_css.stylesheet_href(
                os.path.join('api', 'java.base', 'java', 'lang',
                             'String.html'), OLD_SHEETS))

    def test_a_page_outside_the_api_falls_back_to_what_there_is(self):
        self.assertEqual(
            '../../api/offline-simple.css',
            qch_css.stylesheet_href(
                os.path.join('specs', 'man', 'java.html'), OLD_SHEETS))


if __name__ == '__main__':
    unittest.main()
