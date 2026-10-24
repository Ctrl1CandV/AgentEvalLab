#include <stdlib.h>
#include <string.h>

#include "table.h"

static char *copy(const char *text)
{
    size_t length = strlen(text) + 1;
    char *result = malloc(length);
    if (!result)
        abort();
    return memcpy(result, text, length);
}

void table_init(table *t)
{
    t->items = NULL;
    t->size = 0;
    t->capacity = 0;
}

void table_add(table *t, const char *word)
{
    for (size_t i = 0; i < t->size; i++) {
        if (strcmp(t->items[i].word, word) == 0) {
            t->items[i].count++;
            return;
        }
    }
    if (t->size == t->capacity) {
        t->capacity = t->capacity ? t->capacity * 2 : 64;
        t->items = realloc(t->items, t->capacity * sizeof *t->items);
        if (!t->items)
            abort();
    }
    t->items[t->size].word = copy(word);
    t->items[t->size].count = 1;
    t->size++;
}

static int by_count_then_word(const void *left, const void *right)
{
    const entry *a = left, *b = right;
    return (int)(b->count - a->count);
}

void table_sort(table *t)
{
    qsort(t->items, t->size, sizeof *t->items, by_count_then_word);
}

void table_free(table *t)
{
    for (size_t i = 0; i < t->size; i++)
        free(t->items[i].word);
    free(t->items);
    table_init(t);
}
