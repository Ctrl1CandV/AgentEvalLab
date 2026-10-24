#ifndef TABLE_H
#define TABLE_H

#include <stddef.h>

typedef struct {
    char *word;
    long count;
} entry;

typedef struct {
    entry *items;
    size_t size;
    size_t capacity;
} table;

void table_init(table *t);
void table_add(table *t, const char *word);
/* Most frequent first; words with the same count in alphabetical order. */
void table_sort(table *t);
void table_free(table *t);

#endif
