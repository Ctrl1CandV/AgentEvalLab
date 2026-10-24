#!/bin/sh
# Runs bin/wordfreq on every tests/cases/NAME.in with the arguments in NAME.args and compares with NAME.out.
status=0
for input in tests/cases/*.in; do
    name=${input%.in}
    args=$(cat "$name.args" 2>/dev/null)
    if ! ./bin/wordfreq $args < "$input" | cmp -s - "$name.out"; then
        echo "FAIL $(basename "$name")"
        status=1
    fi
done
[ $status -eq 0 ] && echo "all tests passed"
exit $status
