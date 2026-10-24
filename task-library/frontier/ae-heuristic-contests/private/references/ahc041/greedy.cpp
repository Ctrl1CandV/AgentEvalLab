// AHC041 greedy reference: take the least beautiful unassigned vertex as a root and grow its tree depth-first through
// unassigned neighbours, the least beautiful first, so that long paths reach down to height H and the beautiful vertices
// sit deep; repeat until every vertex is in a tree.
#include <bits/stdc++.h>
int n, m, H;
std::vector<int> beauty, parent, depth;
std::vector<std::vector<int>> adjacent;
void grow(int v) {
    if (depth[v] == H) return;
    std::vector<int> next = adjacent[v];
    std::sort(next.begin(), next.end(), [](int a, int b) { return beauty[a] < beauty[b]; });
    for (int u : next) if (parent[u] == -2) { parent[u] = v; depth[u] = depth[v] + 1; grow(u); }
}
int main() {
    std::cin >> n >> m >> H;
    beauty.resize(n); parent.assign(n, -2); depth.assign(n, 0); adjacent.resize(n);
    for (auto& value : beauty) std::cin >> value;
    for (int i = 0; i < m; i++) { int u, v; std::cin >> u >> v; adjacent[u].push_back(v); adjacent[v].push_back(u); }
    std::vector<int> order(n);
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(), [](int a, int b) { return beauty[a] < beauty[b]; });
    for (int root : order) if (parent[root] == -2) { parent[root] = -1; depth[root] = 0; grow(root); }
    for (int v = 0; v < n; v++) std::printf("%d%c", parent[v], v + 1 < n ? ' ' : '\n');
}
