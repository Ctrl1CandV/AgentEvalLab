// AHC026 greedy reference: carry the boxes out in order; when a box is buried, move the boxes above it in one block to
// the stack whose smallest box is largest (an empty stack counts as the largest), so that the block buries the boxes
// that are needed last.
#include <bits/stdc++.h>
int main() {
    int n, m; std::cin >> n >> m;
    std::vector<std::vector<int>> stacks(m, std::vector<int>(n / m));
    for (auto& stack : stacks) for (auto& box : stack) std::cin >> box;
    std::vector<std::pair<int, int>> ops;
    for (int v = 1; v <= n; v++) {
        int s = 0, p = 0;
        for (int i = 0; i < m; i++) for (int j = 0; j < (int)stacks[i].size(); j++) if (stacks[i][j] == v) { s = i; p = j; }
        if (p + 1 < (int)stacks[s].size()) {
            int best = -1, bestMin = -1;
            for (int i = 0; i < m; i++) {
                if (i == s) continue;
                int least = stacks[i].empty() ? INT_MAX : *std::min_element(stacks[i].begin(), stacks[i].end());
                if (least > bestMin) { bestMin = least; best = i; }
            }
            ops.push_back({stacks[s][p + 1], best + 1});
            stacks[best].insert(stacks[best].end(), stacks[s].begin() + p + 1, stacks[s].end());
            stacks[s].resize(p + 1);
        }
        ops.push_back({v, 0});
        stacks[s].pop_back();
    }
    for (auto [v, i] : ops) std::printf("%d %d\n", v, i);
}
