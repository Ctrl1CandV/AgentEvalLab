// AHC035 reference: every turn, plant the N*N seeds of highest value in row-major order (valid, ignores how seeds combine).
#include <bits/stdc++.h>
int main() {
    int n, m, t; std::cin >> n >> m >> t;
    int seeds = 2 * n * (n - 1);
    std::vector<std::vector<int>> x(seeds, std::vector<int>(m));
    for (int turn = 0; turn < t; turn++) {
        for (auto& row : x) for (auto& value : row) std::cin >> value;
        std::vector<int> order(seeds);
        std::iota(order.begin(), order.end(), 0);
        std::sort(order.begin(), order.end(), [&](int a, int b) {
            return std::accumulate(x[a].begin(), x[a].end(), 0) > std::accumulate(x[b].begin(), x[b].end(), 0);
        });
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) std::cout << order[i * n + j] << (j + 1 < n ? ' ' : '\n');
        }
        std::cout << std::flush;
    }
    for (auto& row : x) for (auto& value : row) std::cin >> value;
}
