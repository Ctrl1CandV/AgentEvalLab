PYTHON ?= python3
RAW_SALES := $(wildcard raw/sales-*.csv)

report.csv: build/joined.csv scripts/report.py
	$(PYTHON) scripts/report.py build/joined.csv > $@

build/joined.csv: build/sales.csv raw/stores.csv scripts/join.py
	$(PYTHON) scripts/join.py build/sales.csv raw/stores.csv > $@

build/sales.csv: $(RAW_SALES) scripts/normalize.sh
	@mkdir -p build
	sh scripts/normalize.sh $(RAW_SALES) > $@

test: report.csv
	$(PYTHON) -m unittest discover -s tests

clean:
	rm -rf build report.csv

.PHONY: test clean
