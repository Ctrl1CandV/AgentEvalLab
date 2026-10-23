#include <bits/stdc++.h>
using namespace std;
int main(){int n;cin>>n;const int G=50;vector<vector<int>> c(G,vector<int>(G));
for(int i=0;i<2*n;i++){long x,y;cin>>x>>y;int gx=min<long>(G-1,x*G/100001),gy=min<long>(G-1,y*G/100001);c[gx][gy]+= i<n?1:-1;}
// best rectangle of cells (max-sum submatrix), perimeter within 4e5 automatically (<=4e5)
long best=LONG_MIN;int bx0=0,bx1=0,by0=0,by1=0;
for(int x0=0;x0<G;x0++){vector<long> col(G,0);for(int x1=x0;x1<G;x1++){for(int y=0;y<G;y++)col[y]+=c[x1][y];long cur=0;int s=0;for(int y=0;y<G;y++){if(cur<=0){cur=0;s=y;}cur+=col[y];if(cur>best){best=cur;bx0=x0;bx1=x1;by0=s;by1=y;}}}}
long X0=(long)bx0*100000/G,X1=(long)(bx1+1)*100000/G,Y0=(long)by0*100000/G,Y1=(long)(by1+1)*100000/G;
printf("4\n%ld %ld\n%ld %ld\n%ld %ld\n%ld %ld\n",X0,Y0,X1,Y0,X1,Y1,X0,Y1);}
