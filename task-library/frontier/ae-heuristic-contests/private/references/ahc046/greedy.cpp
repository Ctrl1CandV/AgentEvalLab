// AHC046 greedy reference: for each target in turn, the fewest moves and slides that reach it on the empty rink (a
// breadth-first search over squares; slides stop at the walls). Never places a block.
#include <bits/stdc++.h>
int main() {
    int n, m; std::cin >> n >> m;
    std::vector<std::pair<int, int>> p(m);
    for (auto& [i, j] : p) std::cin >> i >> j;
    const int di[4] = {-1, 1, 0, 0}, dj[4] = {0, 0, -1, 1};
    const char names[4] = {'U', 'D', 'L', 'R'};
    for (int k = 1; k < m; k++) {
        std::vector<int> previous(n * n, -1), action(n * n, -1);
        std::vector<bool> seen(n * n, false);
        std::queue<int> queue;
        int start = p[k - 1].first * n + p[k - 1].second, goal = p[k].first * n + p[k].second;
        seen[start] = true; queue.push(start);
        while (!queue.empty()) {
            int cell = queue.front(); queue.pop();
            if (cell == goal) break;
            int i = cell / n, j = cell % n;
            for (int d = 0; d < 4; d++) for (int slide = 0; slide < 2; slide++) {
                int ni = i, nj = j;
                if (slide) { while (ni + di[d] >= 0 && ni + di[d] < n && nj + dj[d] >= 0 && nj + dj[d] < n) { ni += di[d]; nj += dj[d]; } }
                else { ni += di[d]; nj += dj[d]; if (ni < 0 || ni >= n || nj < 0 || nj >= n) continue; }
                int next = ni * n + nj;
                if (seen[next]) continue;
                seen[next] = true; previous[next] = cell; action[next] = d * 2 + slide; queue.push(next);
            }
        }
        std::vector<int> path;
        for (int cell = goal; cell != start; cell = previous[cell]) path.push_back(action[cell]);
        for (auto it = path.rbegin(); it != path.rend(); ++it) std::printf("%c %c\n", (*it % 2) ? 'S' : 'M', names[*it / 2]);
    }
}
