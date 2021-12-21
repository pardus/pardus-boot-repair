DESTDIR=/
PREFIX=/usr
build:
	: Please run make install
install:
	mkdir -p $(DESTDIR)//usr/bin/ || true
	mkdir -p $(DESTDIR)/usr/share/applications || true
	mkdir -p $(DESTDIR)/usr/share/icons || true
	mkdir -p $(DESTDIR)/usr/share/polkit-1/actions || true
	install main.sh $(DESTDIR)/bin/pardus-boot-repair
	install tr.org.pardus.boot-repair.desktop $(DESTDIR)/$(PREFIX)/share/applications
	install pardus-boot-repair.svg $(DESTDIR)/usr/share/icons/
	install scripts/* $(DESTDIR)/usr/bin/
	install pardus-boot-repair.policy $(DESTDIR)/usr/share/polkit-1/actions/
