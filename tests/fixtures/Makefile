CXX = g++
CXXFLAGS = -g -O0 -std=c++17

all: sample segfault

sample: sample.cpp
	$(CXX) $(CXXFLAGS) -o $@ $<

segfault: segfault.cpp
	$(CXX) $(CXXFLAGS) -o $@ $<

clean:
	rm -f sample segfault

.PHONY: all clean
