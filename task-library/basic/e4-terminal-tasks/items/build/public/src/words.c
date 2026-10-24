#include <ctype.h>

#include "words.h"

#define MAX_WORD 128

void each_word(FILE *in, void (*emit)(const char *word, void *context), void *context)
{
    char word[MAX_WORD];
    size_t length = 0;
    int c;

    while ((c = fgetc(in)) != EOF) {
        if (isalpha(c) || c == '\'') {
            if (length < MAX_WORD - 1)
                word[length++] = (char)tolower(c);
        } else if (length > 0) {
            word[length] = '\0';
            emit(word, context);
            length = 0;
        }
    }
}
