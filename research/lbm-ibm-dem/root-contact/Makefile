CXX ?= c++
FLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
SOLVER ?= ../../solver
.PHONY: test bench clean native
bin/%: %.cpp geometry.hpp search.hpp traction.hpp
	mkdir -p bin
	$(CXX) $(FLAGS) $< -o $@
test: bin/test bin/extra
	./bin/test
	./bin/extra
bench: bin/benchmark
	./bin/benchmark
bin/native_probe: native_probe.cpp geometry.hpp search.hpp traction.hpp $(SOLVER)/src/dem.cpp
	mkdir -p bin
	$(CXX) $(FLAGS) -I$(SOLVER)/include native_probe.cpp $(SOLVER)/src/dem.cpp -o $@
native: bin/native_probe
	./bin/native_probe tip cached 6000
clean:
	rm -rf bin
.PHONY: growth
bin/growth_cell: growth_cell.cpp geometry.hpp search.hpp traction.hpp $(SOLVER)/src/dem.cpp
	mkdir -p bin
	$(CXX) $(FLAGS) -I$(SOLVER)/include growth_cell.cpp $(SOLVER)/src/dem.cpp -o $@
growth: bin/growth_cell
	./bin/growth_cell cached 8000
