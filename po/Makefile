#!/usr/bin/make -f

POTFILES := $(shell cat POTFILES.in)

all: generate-locales

generate-pot: POTFILES.in
	xgettext -o pardus-boot-repair.pot  -L Shell --keyword --keyword=eval_gettext ../pardus-boot-repair

generate-locales:
	for i in $$(find $$1 -name "*.po"); do \
		code=$$(echo $$i | sed 's/.po//'); \
		mkdir -p locale/$$code/LC_MESSAGES/; \
	msgfmt -o locale/$$code/LC_MESSAGES/pardus-boot-repair.mo $$i; \
	done; \
	cp -R locale/* ../usr/share/locale/

update-po:
	for i in *.po; do \
		code=$$(echo $$i | sed 's/.po//'); \
		intltool-update --gettext-package=pardus-boot-repair --dist $$code; \
	done

# vim:ts=4
