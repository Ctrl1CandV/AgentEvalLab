# wordfreq

Prints the most frequent words of a text: `bin/wordfreq [-n N] [file]` reads the file, or standard input, and prints the N most frequent words (default 10), one per line as `count word`. A word is a run of letters and apostrophes, lower-cased. Words with the same count are listed alphabetically.

    make          # builds bin/wordfreq
    make test     # runs the cases in tests/cases
    make clean    # removes everything the build creates
