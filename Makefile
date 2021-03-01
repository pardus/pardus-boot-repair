DESTDIR=/
PREFIX=/usr
build:
	: Please run make install
install:
	mkdir -p $(DESTDIR)/bin/ || true
	mkdir -p $(DESTDIR)/usr/share/applications || true
	install pardus-boot-repair $(DESTDIR)/bin/
	install repair.desktop $(DESTDIR)/$(PREFIX)/share/applications
