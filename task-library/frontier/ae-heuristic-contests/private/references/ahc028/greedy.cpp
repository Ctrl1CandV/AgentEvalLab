// AHC028 greedy reference: build one text by always appending the remaining string that overlaps most with the end of
// the text so far (strings already inside the text are dropped), then type that text at the least cost: a dynamic
// programme over the keys that carry each letter.
#include <bits/stdc++.h>
int main() {
    int n, m, si, sj; std::cin >> n >> m >> si >> sj;
    std::vector<std::string> grid(n);
    for (auto& row : grid) std::cin >> row;
    std::vector<std::string> words(m);
    for (auto& word : words) std::cin >> word;
    std::string text;
    std::vector<bool> used(m, false);
    for (int step = 0; step < m; step++) {
        int best = -1, bestOverlap = -1;
        for (int k = 0; k < m; k++) {
            if (used[k]) continue;
            if (text.find(words[k]) != std::string::npos) { used[k] = true; continue; }
            int overlap = 0;
            for (int length = std::min<int>(words[k].size(), text.size()); length > 0; length--)
                if (text.compare(text.size() - length, length, words[k], 0, length) == 0) { overlap = length; break; }
            if (overlap > bestOverlap) { bestOverlap = overlap; best = k; }
        }
        if (best < 0) break;
        used[best] = true;
        text += words[best].substr(bestOverlap);
    }
    std::vector<std::vector<std::pair<int, int>>> keys(26);
    for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) keys[grid[i][j] - 'A'].push_back({i, j});
    int length = text.size();
    std::vector<std::vector<int>> cost(length), from(length);
    for (int position = 0; position < length; position++) {
        auto& here = keys[text[position] - 'A'];
        cost[position].assign(here.size(), INT_MAX);
        from[position].assign(here.size(), -1);
        for (int a = 0; a < (int)here.size(); a++) {
            if (position == 0) { cost[0][a] = std::abs(here[a].first - si) + std::abs(here[a].second - sj) + 1; continue; }
            auto& before = keys[text[position - 1] - 'A'];
            for (int b = 0; b < (int)before.size(); b++) {
                int value = cost[position - 1][b] + std::abs(here[a].first - before[b].first) + std::abs(here[a].second - before[b].second) + 1;
                if (value < cost[position][a]) { cost[position][a] = value; from[position][a] = b; }
            }
        }
    }
    std::vector<int> choice(length);
    choice[length - 1] = std::min_element(cost[length - 1].begin(), cost[length - 1].end()) - cost[length - 1].begin();
    for (int position = length - 1; position > 0; position--) choice[position - 1] = from[position][choice[position]];
    for (int position = 0; position < length; position++) {
        auto key = keys[text[position] - 'A'][choice[position]];
        std::printf("%d %d\n", key.first, key.second);
    }
}
