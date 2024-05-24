DESTDIR=/
PREFIX=/usr
SUBDIRS := po
build:
	make -C po build
install:
	mkdir -p $(DESTDIR)/$(PREFIX)/bin/ || true
	mkdir -p $(DESTDIR)/$(PREFIX)/share/applications || true
	mkdir -p $(DESTDIR)/$(PREFIX)/share/icons || true
	mkdir -p $(DESTDIR)/$(PREFIX)/share/polkit-1/actions || true
	install pardus-boot-repair $(DESTDIR)/$(PREFIX)/bin/
	install tr.org.pardus.boot-repair.desktop $(DESTDIR)/$(PREFIX)/share/applications
	install pardus-boot-repair.svg $(DESTDIR)/$(PREFIX)/share/icons/
	install scripts/* $(DESTDIR)/$(PREFIX)/bin/
	install pardus-boot-repair.policy $(DESTDIR)/$(PREFIX)/share/polkit-1/actions/
	mkdir -p $(DESTDIR)/$(PREFIX)/share/locale  || true
	cp -a po $(DESTDIR)/.
	# po generation
	make -C po install
pot:
	make -C po generate-pot
	make -C po update-po

clean:
	make -C po clean