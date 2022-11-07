ESTDIR=/
PREFIX=/usr
SUBDIRS := po
build:
	make -C po build
install:
	mkdir -p $(DESTDIR)/usr/bin/ || true
	mkdir -p $(DESTDIR)/usr/share/applications || true
	mkdir -p $(DESTDIR)/usr/share/icons || true
	mkdir -p $(DESTDIR)/usr/share/polkit-1/actions || true
	install pardus-boot-repair $(DESTDIR)/usr/bin/
	install tr.org.pardus.boot-repair.desktop $(DESTDIR)/$(PREFIX)/share/applications
	install pardus-boot-repair.svg $(DESTDIR)/usr/share/icons/
	install scripts/* $(DESTDIR)/usr/bin/
	install pardus-boot-repair.policy $(DESTDIR)/usr/share/polkit-1/actions/
	mkdir -p $(DESTDIR)/usr/share/locale  || true
	cp -a po $(DESTDIR)/.
	# po generation
	make -C po install
pot:
	make -C po generate-pot
	make -C po update-po

clean:
	make -C po clean