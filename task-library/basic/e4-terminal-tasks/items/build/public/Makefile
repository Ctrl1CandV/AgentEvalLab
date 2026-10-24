CC = cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -O2 -Isrc
OBJ = obj/main.o obj/words.o

bin/wordfreq: $(OBJ)
	@mkdir -p bin
	$(CC) $(CFLAGS) -o $@ $(OBJ)

obj/%.o: src/%.c src/words.h src/table.h
        @mkdir -p obj
	$(CC) $(CFLAGS) -c -o $@ $<

test: bin/wordfreq
	./tests/run.sh

clean:
	rm -rf bin

.PHONY: test clean
