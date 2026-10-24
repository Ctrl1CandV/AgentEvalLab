// AHC032 greedy reference: press, one at a time, the stamp and place that raise the board's score the most, while some
// press still raises it and presses remain.
#include <bits/stdc++.h>
const long long MOD = 998244353;
int main() {
    int n, m, k; std::cin >> n >> m >> k;
    std::vector<std::vector<long long>> board(n, std::vector<long long>(n));
    for (auto& row : board) for (auto& cell : row) std::cin >> cell;
    std::vector<std::array<std::array<long long, 3>, 3>> stamps(m);
    for (auto& stamp : stamps) for (auto& row : stamp) for (auto& cell : row) std::cin >> cell;
    std::vector<std::array<int, 3>> ops;
    for (int step = 0; step < k; step++) {
        long long bestGain = 0; int bm = -1, bp = -1, bq = -1;
        for (int s = 0; s < m; s++) for (int p = 0; p + 3 <= n; p++) for (int q = 0; q + 3 <= n; q++) {
            long long gain = 0;
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) gain += (board[p + i][q + j] + stamps[s][i][j]) % MOD - board[p + i][q + j];
            if (gain > bestGain) { bestGain = gain; bm = s; bp = p; bq = q; }
        }
        if (bm < 0) break;
        for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) board[bp + i][bq + j] = (board[bp + i][bq + j] + stamps[bm][i][j]) % MOD;
        ops.push_back({bm, bp, bq});
    }
    std::printf("%d\n", (int)ops.size());
    for (auto& op : ops) std::printf("%d %d %d\n", op[0], op[1], op[2]);
}
