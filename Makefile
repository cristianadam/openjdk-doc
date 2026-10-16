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

SHELL := /usr/bin/env bash

# The feature release of the JDK whose documentation is built.  Any release
# Oracle still has a download page for will do: `make source JDK_VERSION=21`.
JDK_VERSION = 25

python = python3

# Qt keeps this out of the way -- /usr/lib/qt6/libexec on Debian,
# $(brew --prefix qt)/share/qt/libexec on macOS -- so it is usually not on
# PATH.  Say where it is: `make doc_qch qhelpgenerator=/path/to/it`.
qhelpgenerator = qhelpgenerator

#Common prefixes

prefix = /usr
datarootdir = $(prefix)/share
docdir = $(datarootdir)/openjdk-doc/doc

#Naming

NAME = openjdk-doc-en-java$(JDK_VERSION)
TITLE = Java SE $(JDK_VERSION) & JDK $(JDK_VERSION) Documentation
NAMESPACE = org.openjdk.javase.$(JDK_VERSION)
VIRTUAL_FOLDER = javase$(JDK_VERSION)

# The update release the bundle turned out to hold -- 25.0.4 for a 25 -- which
# `fetch_docs.py` leaves behind.  It names the release archives, so that two
# of them from different updates do not have the same name.
RELEASE := $(strip $(shell cat reference/RELEASE 2>/dev/null))
VERSION := $(if $(RELEASE),$(RELEASE),$(JDK_VERSION))

SRC = reference/docs
OUT = output/docs_qch
QCH = output/$(NAME).qch

#STANDARD RULES

all: doc_qch

DISTFILES= \
		commands/               \
		tests/                  \
		build_qhp.py            \
		fetch_docs.py           \
		preprocess_qch.py       \
		qch-dark.css            \
		qch-viewer.css          \
		config/                 \
		requirements.txt        \
		Makefile                \
		LICENSE                 \
		README.md

CLEANFILES = output

TAR_FORMAT := gz
TAR_OPTION := z
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
	TAR_FORMAT := xz
	TAR_OPTION := J
endif

clean:
	rm -rf $(CLEANFILES)

# Also throws away the copy of the documentation, which has to be downloaded
# again afterwards.
distclean: clean
	rm -rf reference

check:
	$(python) -m flake8 --config=config/flake8rc *.py commands tests
	$(python) -m unittest discover

dist: clean
	mkdir -p "openjdk-doc-$(VERSION)"
	cp -r $(DISTFILES) "openjdk-doc-$(VERSION)"
	tar c$(TAR_OPTION)f "openjdk-doc-$(VERSION).tar.$(TAR_FORMAT)" "openjdk-doc-$(VERSION)"
	rm -rf "openjdk-doc-$(VERSION)"

install: install_qch

install_qch: doc_qch
	install -DT -m 644 "$(QCH)" "$(DESTDIR)$(docdir)/qch/$(NAME).qch"

uninstall:
	rm -rf "$(DESTDIR)$(docdir)"

release: doc_qch
	rm -rf release
	mkdir -p release

	pushd "output" > /dev/null; \
	tar c$(TAR_OPTION)f "../release/qch-book-$(VERSION).tar.$(TAR_FORMAT)" "$(NAME).qch"; \
	zip -qr "../release/qch-book-$(VERSION).zip" "$(NAME).qch"; \
	popd > /dev/null

#WORKER RULES

doc_qch: $(QCH)

#the .qch (Qt Help) archive
$(QCH): output/qch-help-project.xml
	#qhelpgenerator only works if the project file is in the same directory
	#as the documentation
	cp "output/qch-help-project.xml" "$(OUT)/qch.qhp"

	pushd "$(OUT)" > /dev/null; \
	$(qhelpgenerator) "qch.qhp" -o "../$(NAME).qch"; \
	popd > /dev/null

	rm -f "$(OUT)/qch.qhp"

#the contents, the index and the file list
output/qch-help-project.xml: $(OUT)
	$(python) build_qhp.py --docs "$(SRC)" --src "$(OUT)" \
		--dst "output/qch-help-project.xml" \
		--title "$(TITLE)" --namespace "$(NAMESPACE)" \
		--virtual-folder "$(VIRTUAL_FOLDER)" \
		--filter-attribute java \
		--filter-attribute "$(JDK_VERSION)"

#the pages, rewritten for a help viewer
$(OUT):
	$(python) preprocess_qch.py --src "$(SRC)" --dst "$(OUT)"

#downloads the documentation bundle Oracle publishes
source:
	$(python) fetch_docs.py --version "$(JDK_VERSION)" --dst reference

	#what was built from the bundle that was here before is not what this
	#one would build, and make judges the tree by whether it is there
	rm -rf "$(OUT)" "output/qch-help-project.xml"

.PHONY: all clean distclean check dist install install_qch uninstall \
	release doc_qch source
