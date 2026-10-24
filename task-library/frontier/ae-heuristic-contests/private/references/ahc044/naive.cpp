// AHC044 naive reference: employee i hands the duty to employee i+1 either way, so the duty goes round in a circle.
// Valid, and ignores the targets.
#include <bits/stdc++.h>
int main() {
    int n, l; std::cin >> n >> l;
    for (int i = 0; i < n; i++) { int t; std::cin >> t; }
    for (int i = 0; i < n; i++) std::printf("%d %d\n", (i + 1) % n, (i + 1) % n);
}
