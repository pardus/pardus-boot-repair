#!/usr/bin/make -f
DESTDIR ?= /
PREFIX ?= /usr
BIN_DIR := $(DESTDIR)$(PREFIX)/bin
SHARE_DIR := $(DESTDIR)$(PREFIX)/share/pardus/pardus-boot-repair
ICON_DIR := $(DESTDIR)$(PREFIX)/share/icons
POLKIT_DIR := $(DESTDIR)$(PREFIX)/share/polkit-1/actions
LOCALE_DIR := $(DESTDIR)$(PREFIX)/share/locale
DESKTOP_DIR := $(DESTDIR)$(PREFIX)/share/applications

.PHONY: all build install buildmo pot gresource clean run

all: build

install: gresource
	install -d $(BIN_DIR)
	install pardus-boot-repair $(BIN_DIR)
	install src/scripts/* $(BIN_DIR)
	install -d $(SHARE_DIR)
	cp -a src/* $(SHARE_DIR)
	install -d $(ICON_DIR)
	install src/data/images/pardus-boot-repair.svg $(ICON_DIR)
	install -d $(POLKIT_DIR)
	install -d $(DESKTOP_DIR)
	install src/data/tr.org.pardus-boot-repair.policy $(POLKIT_DIR)
	install src/data/tr.org.pardus-boot-repair.desktop $(DESKTOP_DIR)

	@for file in $(wildcard po/*.po); do \
		lang=$$(basename $$file .po); \
		install -d $(LOCALE_DIR)/$$lang/LC_MESSAGES/; \
		install mo/$$lang.mo $(LOCALE_DIR)/$$lang/LC_MESSAGES/pardus-boot-repair.mo; \
	done

build: gresource buildmo

gresource:
	(cd src/data && glib-compile-resources tr.org.pardus.boot-repair.gresource.xml)

buildmo:
	@echo "Building .mo files..."
	install -d mo
	@for file in $(wildcard po/*.po); do \
		lang=$$(basename $$file .po); \
		msgfmt -o mo/$$lang.mo $$file; \
	done

pot:
	xgettext -o po/pardus-boot-repair.pot --from-code=utf-8 src/data/ui/*.ui src/*.py
	@for file in $(wildcard po/*.po); do \
		msgmerge $$file po/pardus-boot-repair.pot -o $$file.new; \
		rm -f $$file; \
		mv $$file.new $$file; \
	done

clean:
	rm -f src/data/tr.org.pardus.boot-repair.gresource
	rm -rf mo

run: gresource
	python3 src/Main.py
