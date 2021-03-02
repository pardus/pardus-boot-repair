DESTDIR=/
PREFIX=/usr
build:
	: Please run make install
install:
	mkdir -p $(DESTDIR)/bin/ || true
	mkdir -p $(DESTDIR)/usr/share/applications || true
	mkdir -p $(DESTDIR)/usr/share/icons || true
	install pardus-boot-repair $(DESTDIR)/bin/
	install tr.org.pardus.boot-repair.desktop $(DESTDIR)/$(PREFIX)/share/applications
	install pardus-boot-repair.svg $(DESTDIR)/usr/share/icons
