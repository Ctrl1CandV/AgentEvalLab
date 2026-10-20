#!/bin/sh
# Turns the regional sales exports into one file of date,amount,store rows (see README.md).
echo "date,amount,store"
for file in "$@"; do
    case "$file" in
        */sales-eu*) awk 'NR > 1 { sub(/\r$/, ""); if ($0 == "") next; gsub(/,/, "."); gsub(/;/, ","); print }' "$file" ;;
        *) awk 'NR > 1 { sub(/\r$/, ""); if ($0 == "") next; print }' "$file" ;;
    esac
done
