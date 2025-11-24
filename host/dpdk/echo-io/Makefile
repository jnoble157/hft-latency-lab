CC ?= gcc
CFLAGS += -O3 -march=native -Wall -Wextra -Wno-unused-parameter
CFLAGS += $(shell pkg-config --cflags libdpdk 2>/dev/null)
LDFLAGS += $(shell pkg-config --libs libdpdk 2>/dev/null)

BIN := echo-io
SRC := main.c

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(BIN)

.PHONY: all clean


