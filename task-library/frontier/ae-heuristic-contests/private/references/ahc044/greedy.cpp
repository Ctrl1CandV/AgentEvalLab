// AHC044 greedy reference: each employee passes half of their turns to a_i and half to b_i, so each of the 2N hand-offs
// carries about T_i / 2 turns; give the hand-offs, largest first, to the employee whose target is least covered so far.
#include <bits/stdc++.h>
int main() {
    int n, l; std::cin >> n >> l;
    std::vector<long long> target(n);
    for (auto& t : target) std::cin >> t;
    std::vector<std::pair<long long, int>> handoffs;   // (turns carried, slot: 2 i + 0 for a_i, + 1 for b_i)
    for (int i = 0; i < n; i++) { handoffs.push_back({target[i] / 2, 2 * i}); handoffs.push_back({target[i] - target[i] / 2, 2 * i + 1}); }
    std::sort(handoffs.rbegin(), handoffs.rend());
    std::vector<long long> covered(n, 0);
    std::vector<int> to(2 * n);
    for (auto [turns, slot] : handoffs) {
        int best = 0;
        for (int y = 1; y < n; y++) if (target[y] - covered[y] > target[best] - covered[best]) best = y;
        to[slot] = best;
        covered[best] += turns;
    }
    for (int i = 0; i < n; i++) std::printf("%d %d\n", to[2 * i], to[2 * i + 1]);
}
