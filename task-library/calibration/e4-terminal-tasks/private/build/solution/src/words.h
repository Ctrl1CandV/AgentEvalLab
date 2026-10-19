#ifndef WORDS_H
#define WORDS_H

#include <stdio.h>

/* Calls emit(word, context) for every word in the stream: a maximal run of letters and apostrophes, lower-cased.
   Words longer than 127 characters are cut to 127. */
void each_word(FILE *in, void (*emit)(const char *word, void *context), void *context);

#endif
