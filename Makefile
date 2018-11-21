SRC = src
REQUIREMENTS = requirements.txt
PYTHON = python
IPYTHON = ipython
MAIN = radio_select.py

.PHONY: clean ipython run deps

deps: .deps

.deps: $(REQUIREMENTS)
	pip install --upgrade -r $(REQUIREMENTS)
	@touch .deps

clean:
	@echo "Cleaning all artifacts..."
	@-rm -f .deps
	@-find . -name "*.pyc" -delete

ipython: deps
	cd $(SRC); \
	DUMMY=True $(IPYTHON)

run: deps
	$(IPYTHON) $(MAIN)

debug: deps
	$(IPYTHON) --pdb $(MAIN)
