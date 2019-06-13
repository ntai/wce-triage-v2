
DESTDIR := ../wce-triage-ui/public

COMPONENTS := computer.py cpu.py disk.py memory.py network.py optical_drive.py pci.py sensor.py sound.py video.py
OPS := diskop_create_image.py diskop.py diskop_restore.py tasks.py
HTTP := httpserver.py

TOPLEVEL := httpserver.sh

SOURCES := $(TOPLEVEL) $(addprefix components/,$(COMPONENTS)) $(addprefix ops/,$(OPS)) $(addprefix http/,$(HTTP))

TARGETS := $(addprefix $(DESTDIR)/,$(SOURCES))

all: $(TARGETS)

$(TARGETS): $(SOURCES)

$(DESTDIR)/components/%.py : components/%.py
	cp $< $@

$(DESTDIR)/http/%.py : http/%.py
	cp $< $@

$(DESTDIR)/ops/%.py : ops/%.py
	cp $< $@

$(DESTDIR)/%.sh : %.sh
	cp $< $@

.PHONY: clean

clean:
	rm -f $(TARGETS)
