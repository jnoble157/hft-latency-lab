CC ?= gcc
CFLAGS += -O3 -march=native -Wall -Wextra
LDFLAGS += -lm

BIN := replay-udp
SRC := replay-udp.c

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(BIN)

.PHONY: all clean


