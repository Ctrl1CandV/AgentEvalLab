// AHC042 greedy reference: repeatedly take the cheapest safe removal, the Oni and direction with the fewest shifts and
// no Fukunokami between it and the edge (Oni on the way fall off too), and do not shift back, as long as every Oni left
// still has a safe direction afterwards; otherwise shift back as the statement's hint does.
#include <bits/stdc++.h>
int n;
using Board = std::vector<std::string>;
void shift(Board& board, char d, int p) {
    if (d == 'L') { for (int j = 0; j + 1 < n; j++) board[p][j] = board[p][j + 1]; board[p][n - 1] = '.'; }
    if (d == 'R') { for (int j = n - 1; j > 0; j--) board[p][j] = board[p][j - 1]; board[p][0] = '.'; }
    if (d == 'U') { for (int i = 0; i + 1 < n; i++) board[i][p] = board[i + 1][p]; board[n - 1][p] = '.'; }
    if (d == 'D') { for (int i = n - 1; i > 0; i--) board[i][p] = board[i - 1][p]; board[0][p] = '.'; }
}
char opposite(char d) { return d == 'L' ? 'R' : d == 'R' ? 'L' : d == 'U' ? 'D' : 'U'; }
// Safe moves for the Oni at (i, j): (shifts, direction, line).
std::vector<std::tuple<int, char, int>> safe(const Board& board, int i, int j) {
    std::vector<std::tuple<int, char, int>> moves;
    bool up = true, down = true, left = true, right = true;
    for (int k = 0; k < i; k++) up &= board[k][j] != 'o';
    for (int k = i + 1; k < n; k++) down &= board[k][j] != 'o';
    for (int k = 0; k < j; k++) left &= board[i][k] != 'o';
    for (int k = j + 1; k < n; k++) right &= board[i][k] != 'o';
    if (up) moves.push_back({i + 1, 'U', j});
    if (down) moves.push_back({n - i, 'D', j});
    if (left) moves.push_back({j + 1, 'L', i});
    if (right) moves.push_back({n - j, 'R', i});
    return moves;
}
bool allSafe(const Board& board) {
    for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (board[i][j] == 'x' && safe(board, i, j).empty()) return false;
    return true;
}
int main() {
    std::cin >> n;
    Board board(n);
    for (auto& row : board) std::cin >> row;
    std::vector<std::pair<char, int>> ops;
    while (true) {
        int best = INT_MAX; char bd = 0; int bp = 0;
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (board[i][j] == 'x')
            for (auto [k, d, p] : safe(board, i, j)) if (k < best) { best = k; bd = d; bp = p; }
        if (best == INT_MAX) break;
        Board after = board;
        for (int k = 0; k < best; k++) shift(after, bd, bp);
        for (int k = 0; k < best; k++) ops.push_back({bd, bp});
        if (!allSafe(after)) {
            for (int k = 0; k < best; k++) { shift(after, opposite(bd), bp); ops.push_back({opposite(bd), bp}); }
        }
        board = after;
    }
    for (auto [d, p] : ops) std::printf("%c %d\n", d, p);
}
