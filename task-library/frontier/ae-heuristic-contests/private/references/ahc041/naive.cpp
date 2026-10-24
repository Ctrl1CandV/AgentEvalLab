// AHC041 naive reference: every vertex is the root of its own tree. Valid, and every height is 0.
#include <bits/stdc++.h>
int main() {
    int n, m, h; std::cin >> n >> m >> h;
    for (int v = 0; v < n; v++) std::printf("%d%c", -1, v + 1 < n ? ' ' : '\n');
}
