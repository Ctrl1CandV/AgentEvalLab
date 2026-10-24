// AHC042 naive reference: the statement's hint. For each remaining Oni, choose a direction with no Fukunokami between
// it and the edge, shift its row or column until it falls off, then shift back. Valid, and never shares a shift
// between two Oni.
#include <bits/stdc++.h>
int main() {
    int n; std::cin >> n;
    std::vector<std::string> board(n);
    for (auto& row : board) std::cin >> row;
    std::vector<std::pair<char, int>> ops;
    auto shift = [&](char d, int p) {
        ops.push_back({d, p});
        if (d == 'L') { for (int j = 0; j + 1 < n; j++) board[p][j] = board[p][j + 1]; board[p][n - 1] = '.'; }
        if (d == 'R') { for (int j = n - 1; j > 0; j--) board[p][j] = board[p][j - 1]; board[p][0] = '.'; }
        if (d == 'U') { for (int i = 0; i + 1 < n; i++) board[i][p] = board[i + 1][p]; board[n - 1][p] = '.'; }
        if (d == 'D') { for (int i = n - 1; i > 0; i--) board[i][p] = board[i - 1][p]; board[0][p] = '.'; }
    };
    for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) {
        if (board[i][j] != 'x') continue;
        bool up = true, down = true, left = true, right = true;
        for (int k = 0; k < i; k++) up &= board[k][j] != 'o';
        for (int k = i + 1; k < n; k++) down &= board[k][j] != 'o';
        for (int k = 0; k < j; k++) left &= board[i][k] != 'o';
        for (int k = j + 1; k < n; k++) right &= board[i][k] != 'o';
        if (up) { for (int k = 0; k <= i; k++) shift('U', j); for (int k = 0; k <= i; k++) shift('D', j); }
        else if (down) { for (int k = 0; k < n - i; k++) shift('D', j); for (int k = 0; k < n - i; k++) shift('U', j); }
        else if (left) { for (int k = 0; k <= j; k++) shift('L', i); for (int k = 0; k <= j; k++) shift('R', i); }
        else if (right) { for (int k = 0; k < n - j; k++) shift('R', i); for (int k = 0; k < n - j; k++) shift('L', i); }
    }
    for (auto [d, p] : ops) std::printf("%c %d\n", d, p);
}
