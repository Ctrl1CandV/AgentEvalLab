// AHC035 naive reference: every turn, plant seeds 0 to N*N-1 in row-major order (valid, ignores every seed's value).
#include <bits/stdc++.h>
int main() {
    int n, m, t; std::cin >> n >> m >> t;
    int seeds = 2 * n * (n - 1);
    std::vector<int> x(seeds * m);
    for (int turn = 0; turn < t; turn++) {
        for (auto& value : x) std::cin >> value;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) std::cout << i * n + j << (j + 1 < n ? ' ' : '\n');
        }
        std::cout << std::flush;
    }
    for (auto& value : x) std::cin >> value;
}
