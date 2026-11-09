CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -march=native -fopenmp -Wall -Wextra -Wpedantic
CPPFLAGS += -Iinclude
CORE = src/lbm.cpp src/ibm.cpp src/dem.cpp src/near_field.cpp
HEADERS = $(wildcard include/*.hpp)
TESTS = tests/test_main.cpp tests/test_lbm.cpp tests/test_ibm.cpp tests/test_dem.cpp tests/test_ibm_independent.cpp tests/test_block.cpp tests/test_quadrature.cpp tests/test_ibm_prescribed.cpp tests/test_near_field.cpp tests/test_wet_stage.cpp

.PHONY: all test clean
all: bin/ibdem bin/tests bin/wet_impact bin/resistance_probe bin/test_compact_commit bin/test_hydro_contact bin/test_film_port bin/film_conductance

bin/ibdem: $(CORE) src/main.cpp $(HEADERS)
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(CORE) src/main.cpp -o $@

bin/tests: $(CORE) $(TESTS) $(HEADERS)
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(CORE) $(TESTS) -o $@

bin/wet_impact: $(CORE) src/wet_main.cpp $(HEADERS)
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(CORE) src/wet_main.cpp -o $@

bin/resistance_probe: $(CORE) src/resistance_main.cpp $(HEADERS)
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(CORE) src/resistance_main.cpp -o $@

bin/test_compact_commit: $(CORE) tests/test_compact_commit.cpp $(HEADERS)
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(CORE) tests/test_compact_commit.cpp -o $@

bin/test_hydro_contact: $(CORE) tests/test_hydro_contact.cpp $(HEADERS)
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(CORE) tests/test_hydro_contact.cpp -o $@

bin/test_film_port: tests/test_film_port.cpp include/film_port.hpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) tests/test_film_port.cpp -o $@

bin/film_conductance: examples/film_conductance.cpp include/film_port.hpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) examples/film_conductance.cpp -o $@

test: bin/tests bin/test_compact_commit bin/test_hydro_contact bin/test_film_port
	OMP_NUM_THREADS=1 ./bin/tests
	OMP_NUM_THREADS=1 ./bin/test_compact_commit
	OMP_NUM_THREADS=1 ./bin/test_hydro_contact
	OMP_NUM_THREADS=1 ./bin/test_film_port

clean:
	rm -rf bin
