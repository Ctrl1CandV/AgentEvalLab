#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "table.h"
#include "words.h"

static void add(const char *word, void *context)
{
    table_add((table *)context, word);
}

int main(int argc, char **argv)
{
    long limit = 10;
    int verbose = 0;
    const char *path = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-n") == 0 && i + 1 < argc)
            limit = strtol(argv[++i], NULL, 10);
        else
            path = argv[i];
    }
    FILE *in = path ? fopen(path, "r") : stdin;
    if (!in) {
        perror(path);
        return 2;
    }
    table t;
    table_init(&t);
    each_word(in, add, &t);
    if (path)
        fclose(in);
    table_sort(&t);
    for (size_t i = 0; i < t.size && (long)i < limit; i++)
        printf("%ld %s\n", t.items[i].count, t.items[i].word);
    table_free(&t);
    return 0;
}
