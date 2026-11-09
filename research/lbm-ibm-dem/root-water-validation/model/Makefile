CXX ?= c++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra -Wpedantic
PYTHON ?= python3
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
.PHONY: all test run core-test figures verify sensitivity diagnostics
all: bin/rhizoprobe
bin/rhizoprobe: applications/rhizofield/probe.cpp solver/src/dem.cpp solver/include/dem.hpp solver/include/common.hpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) -Isolver/include applications/rhizofield/probe.cpp solver/src/dem.cpp -o $@
core-test:
	$(MAKE) -C solver test
run: all
	$(PYTHON) -m applications.rhizofield.run --output results
sensitivity: all
	$(PYTHON) -m applications.rhizofield.run --output results/time_refinement --steps 36 --nopen 18
	$(PYTHON) -m applications.rhizofield.run --output results/space_refinement --grid-scale 2
	$(MAKE) diagnostics
diagnostics:
	$(PYTHON) -m applications.rhizofield.refine --output results
	$(PYTHON) -m applications.rhizofield.diagnose --output results
figures:
	$(PYTHON) figures/plot.py
verify:
	$(MAKE) test
	$(MAKE) core-test
	$(MAKE) run
	$(MAKE) sensitivity
	$(MAKE) figures
test: all
	$(PYTHON) -m unittest discover -s tests -v

.PHONY: calibrate calibrated-pairs
calibrate: all
	$(PYTHON) -m calibration.fit
	$(PYTHON) -m calibration.tissue
	$(PYTHON) -m calibration.matched_inventory
calibrated-pairs: calibrate
	$(PYTHON) -m calibration.coupled --scale 1
	$(PYTHON) -m calibration.coupled --scale 2
	$(PYTHON) -m calibration.coupled --case cup_transfer
	$(PYTHON) -m calibration.coupled --case grapevine_not_soaked
	$(PYTHON) -m calibration.coupled --case grapevine_soaked_24h
	$(PYTHON) -m calibration.angle_sensitivity

.PHONY: root-contact-test root-contact-bench root-contact-native
root-contact-test:
	$(MAKE) -C applications/root_contact test
root-contact-bench:
	$(MAKE) -C applications/root_contact bench
root-contact-native:
	$(MAKE) -C applications/root_contact native growth
test: root-contact-test

.PHONY: root-contact-integration-test root-contact-review
root-contact-integration-test:
	$(MAKE) -C applications/root_contact integration-test
root-contact-review:
	$(PYTHON) applications/root_contact/run_review.py --output review_evidence
test: root-contact-integration-test

.PHONY: audit-areas
audit-areas:
	$(PYTHON) -m unittest discover -s validation_water/volume_mapping -p test_volume_mapping.py -v
	$(PYTHON) validation_water/volume_mapping/volume_mapping.py
