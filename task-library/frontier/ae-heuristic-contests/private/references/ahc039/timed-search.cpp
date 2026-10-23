// AHC039 reference: the best rectangle on a fine grid, improved by random moves of its sides for 1.8 s (uses the time
// limit, for the judge's timing calibration).
#include <bits/stdc++.h>
using namespace std;
int main() {
    auto start = chrono::steady_clock::now();
    int n; cin >> n; const int G = 400;
    vector<vector<int>> c(G + 1, vector<int>(G + 1, 0));
    for (int i = 0; i < 2 * n; i++) { long x, y; cin >> x >> y; int gx = min<long>(G - 1, x * G / 100001), gy = min<long>(G - 1, y * G / 100001); c[gx + 1][gy + 1] += i < n ? 1 : -1; }
    for (int i = 1; i <= G; i++) for (int j = 1; j <= G; j++) c[i][j] += c[i - 1][j] + c[i][j - 1] - c[i - 1][j - 1];
    auto value = [&](int x0, int x1, int y0, int y1) { return c[x1][y1] - c[x0][y1] - c[x1][y0] + c[x0][y0]; };
    mt19937 rng(12345); int bx0 = 0, bx1 = G, by0 = 0, by1 = G; long best = value(bx0, bx1, by0, by1);
    while (chrono::duration<double>(chrono::steady_clock::now() - start).count() < 1.8) {
        int x0 = bx0, x1 = bx1, y0 = by0, y1 = by1, d = rng() % 21 - 10;
        switch (rng() % 4) { case 0: x0 = clamp(x0 + d, 0, x1 - 1); break; case 1: x1 = clamp(x1 + d, x0 + 1, G); break; case 2: y0 = clamp(y0 + d, 0, y1 - 1); break; default: y1 = clamp(y1 + d, y0 + 1, G); }
        long v = value(x0, x1, y0, y1);
        if (v >= best) { best = v; bx0 = x0; bx1 = x1; by0 = y0; by1 = y1; }
    }
    long X0 = (long)bx0 * 100001 / G, X1 = min<long>(100000, (long)bx1 * 100001 / G), Y0 = (long)by0 * 100001 / G, Y1 = min<long>(100000, (long)by1 * 100001 / G);
    printf("4\n%ld %ld\n%ld %ld\n%ld %ld\n%ld %ld\n", X0, Y0, X1, Y0, X1, Y1, X0, Y1);
}
