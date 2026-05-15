# Derived paths based on the DIR variable
TEXFILES := $(wildcard *.tex)
BIBFILES := $(wildcard *.bib)
TEXSRC   := Documentacion.tex
PDFOUT   := build/Documentacion.pdf

.PHONY: all clean

# The main target
all: $(PDFOUT)

$(PDFOUT): $(TEXFILES) $(BIBFILES)
	latexmk -pdf -shell-escape -output-directory=build $(TEXSRC)

clean:
	latexmk -C -output-directory=build $(TEXSRC)
