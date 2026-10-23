#include <bits/stdc++.h>
// Tilt by flavor: flavor 1 forward, 2 left, 3 right (a crude clustering heuristic).
int main(){std::vector<int> f(100);for(auto&x:f)std::cin>>x;for(int t=0;t<100;t++){int p;std::cin>>p;const char* d= f[t]==1?"F":(f[t]==2?"L":"R");std::cout<<d<<std::endl;}}
