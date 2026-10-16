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

# Fetches the documentation the archive is built from.
#
# Oracle publishes the whole of it as one zip -- the API documentation, the
# specifications and a manual page for every tool in the JDK, which is what
# the pages at docs.oracle.com are generated from -- and serves it without
# asking anyone to agree to anything first.  So there is no crawling to do
# here, and the copy we build from is the one Oracle released rather than
# whatever a few thousand requests happened to come back with.
#
# What the zip is called changes with every update release, and the URL
# carries a digest that changes with it, so the download page is read for the
# link rather than the link being spelled out.

import argparse
import os
import re
import shutil
import sys
import zipfile

from urllib.request import Request, urlopen

DOWNLOAD_PAGE = ('https://www.oracle.com/java/technologies/'
                 'javase-jdk%s-doc-downloads.html')

ARCHIVE_RE = re.compile(
    r'https://download\.oracle\.com/[^"\'<>\s]+_doc-all\.zip')

# What the archive is called tells us which update release it holds:
# `jdk-25.0.4_doc-all.zip`.
RELEASE_RE = re.compile(r'jdk-([0-9][0-9.+]*)_doc-all\.zip')

# Oracle's CDN answers a request that names no browser with a redirect to an
# error page, so the download is asked for the way a browser would ask.
USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 '
              'Safari/537.36')

# The directory the zip holds everything under, which is also what the rest
# of the build expects to find under the source root.
BUNDLE_DIR = 'docs'

CHUNK = 1 << 20


def fetch(url):
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def find_archive_url(version):
    page = DOWNLOAD_PAGE % version
    print('Reading %s' % page)

    try:
        text = fetch(page).decode('utf-8', 'replace')
    except OSError as error:
        raise SystemExit('could not read the download page: %s' % error)

    match = ARCHIVE_RE.search(text)
    if match is None:
        raise SystemExit(
            'no documentation archive is linked from %s -- is there a '
            'release of JDK %s?' % (page, version))

    return match.group(0)


def download(url, path):
    print('Downloading %s' % url)
    request = Request(url, headers={'User-Agent': USER_AGENT})

    with urlopen(request) as response:
        total = int(response.headers.get('Content-Length') or 0)
        if response.headers.get_content_type() != 'application/zip':
            raise SystemExit(
                'the download answered with %s rather than a zip; the link '
                'on the download page may have moved'
                % response.headers.get_content_type())

        done = 0
        with open(path, 'wb') as a_file:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                a_file.write(chunk)
                done += len(chunk)
                report(done, total)

    sys.stdout.write('\n')
    print('Wrote %s (%.1f MB)' % (path, os.path.getsize(path) / 1e6))


def report(done, total):
    if not sys.stdout.isatty():
        return
    if total:
        sys.stdout.write('\r  %.0f%% of %.0f MB' % (100 * done / total,
                                                    total / 1e6))
    else:
        sys.stdout.write('\r  %.0f MB' % (done / 1e6))
    sys.stdout.flush()


def extract(archive_path, dest_root):
    # Start from nothing: a bundle left over from another release would be
    # carried into the archive page by page, since the build takes whatever
    # it finds here.
    bundle = os.path.join(dest_root, BUNDLE_DIR)
    if os.path.isdir(bundle):
        print('Removing the previous %s' % bundle)
        shutil.rmtree(bundle)

    print('Unpacking into %s' % dest_root)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = os.path.normpath(os.path.join(dest_root, member.filename))
            if os.path.relpath(target, dest_root).startswith(os.pardir):
                raise SystemExit('the archive names a path outside the '
                                 'destination: %s' % member.filename)
            archive.extract(member, dest_root)

    if not os.path.isdir(bundle):
        raise SystemExit('the archive holds no "%s" directory' % BUNDLE_DIR)

    pages = sum(len([name for name in files if name.endswith('.html')])
                for _, _, files in os.walk(bundle))
    print('Unpacked %d pages' % pages)


def write_release(dest_root, archive_name):
    # The update release the bundle holds, which the Makefile stamps the
    # archive and the help namespace with.
    match = RELEASE_RE.search(archive_name)
    release = match.group(1) if match else ''
    path = os.path.join(dest_root, 'RELEASE')

    with open(path, 'w', encoding='utf-8') as a_file:
        a_file.write(release + '\n')

    return release


def main():
    parser = argparse.ArgumentParser(prog='fetch_docs.py')
    parser.add_argument(
        '--version', default='25',
        help='the feature release of the JDK to fetch the documentation of')
    parser.add_argument(
        '--url',
        help='the documentation archive to fetch, rather than the one linked '
             'from the download page')
    parser.add_argument(
        '--dst', default='reference',
        help='where to unpack it; the bundle lands in <dst>/docs')
    parser.add_argument(
        '--keep-archive', action='store_true',
        help='keep the downloaded zip, and use it again instead of '
             'downloading it a second time')
    args = parser.parse_args()

    url = args.url or find_archive_url(args.version)
    name = url.rsplit('/', 1)[-1].replace('%2B', '+')

    os.makedirs(args.dst, exist_ok=True)
    archive_path = os.path.join(args.dst, name)

    if args.keep_archive and os.path.isfile(archive_path):
        print('Using the archive already here: %s' % archive_path)
    else:
        download(url, archive_path)

    extract(archive_path, args.dst)
    release = write_release(args.dst, name)
    if release:
        print('JDK %s documentation' % release)

    if not args.keep_archive:
        os.remove(archive_path)


if __name__ == '__main__':
    main()
