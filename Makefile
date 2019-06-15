
SRCDIR := wce_triage
DESTDIR := ../wce-triage-ui/public

COMPONENTS := computer.py cpu.py disk.py memory.py network.py optical_drive.py pci.py sensor.py sound.py video.py
OPS := diskop_create_image.py diskop.py diskop_restore.py tasks.py
HTTP := httpserver.py

TOPLEVEL := httpserver.sh

SOURCES := $(addprefix $(SRCDIR)/,$(TOPLEVEL)) $(addprefix $(SRCDIR)/components/,$(COMPONENTS)) $(addprefix $(SRCDIR)/ops/,$(OPS)) $(addprefix $(SRCDIR)/http/,$(HTTP))
TARGETS := $(subst $(SRCDIR),$(DESTDIR),$(SOURCES)) 

all: $(TARGETS)

$(TARGETS): $(SOURCES)

$(DESTDIR)/components/%.py : $(SRCDIR)/components/%.py
	cp $< $@

$(DESTDIR)/http/%.py : $(SRCDIR)/http/%.py
	cp $< $@

$(DESTDIR)/ops/%.py : $(SRCDIR)/ops/%.py
	cp $< $@

$(DESTDIR)/%.sh : $(SRCDIR)/%.sh
	cp $< $@

.PHONY: clean

clean:
	rm -f $(TARGETS)
