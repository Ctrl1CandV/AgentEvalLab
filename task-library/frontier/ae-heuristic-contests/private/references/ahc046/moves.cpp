// AHC046 reference: walk to each target with single moves only (valid, never slides or places blocks).
#include <bits/stdc++.h>
int main() {
    int n, m; std::cin >> n >> m;
    std::vector<std::pair<int, int>> p(m);
    for (auto& [i, j] : p) std::cin >> i >> j;
    for (int k = 1; k < m; k++) {
        auto [i, j] = p[k - 1];
        auto [ti, tj] = p[k];
        while (i < ti) { std::puts("M D"); i++; }
        while (i > ti) { std::puts("M U"); i--; }
        while (j < tj) { std::puts("M R"); j++; }
        while (j > tj) { std::puts("M L"); j--; }
    }
}
