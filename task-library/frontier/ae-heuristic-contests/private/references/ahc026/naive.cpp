// AHC026 naive reference: carry the boxes out in order; when a box is buried, move everything above it onto the next
// stack to the right (cyclically). Valid, and ignores where the moved boxes land.
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
            int d = (s + 1) % m;
            ops.push_back({stacks[s][p + 1], d + 1});
            stacks[d].insert(stacks[d].end(), stacks[s].begin() + p + 1, stacks[s].end());
            stacks[s].resize(p + 1);
        }
        ops.push_back({v, 0});
        stacks[s].pop_back();
    }
    for (auto [v, i] : ops) std::printf("%d %d\n", v, i);
}
