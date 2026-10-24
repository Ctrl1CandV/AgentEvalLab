#!/bin/sh
# Turns the regional sales exports into one file of date,amount,store rows (see README.md).
echo "date,amount,store"
for file in "$@"; do
    tail -n +2 "$file"
done
