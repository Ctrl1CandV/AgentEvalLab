// AHC028 naive reference: type every string in the given order, one after another without overlaps, pressing the
// nearest key with each letter. Valid (every string appears), and ignores shared prefixes and suffixes.
#include <bits/stdc++.h>
int main() {
    int n, m, si, sj; std::cin >> n >> m >> si >> sj;
    std::vector<std::string> grid(n);
    for (auto& row : grid) std::cin >> row;
    std::string text;
    for (int k = 0; k < m; k++) { std::string t; std::cin >> t; text += t; }
    int ci = si, cj = sj;
    for (char c : text) {
        int bi = -1, bj = -1, best = INT_MAX;
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (grid[i][j] == c && std::abs(i - ci) + std::abs(j - cj) < best) { best = std::abs(i - ci) + std::abs(j - cj); bi = i; bj = j; }
        std::printf("%d %d\n", bi, bj);
        ci = bi; cj = bj;
    }
}
