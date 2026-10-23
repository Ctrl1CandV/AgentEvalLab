#include <bits/stdc++.h>
int main(){int n;std::cin>>n;long x,y;std::cin>>x>>y; long a=std::max(0L,x-1),b=std::max(0L,y-1); if(a+2>100000)a=99998; if(b+2>100000)b=99998;
printf("4\n%ld %ld\n%ld %ld\n%ld %ld\n%ld %ld\n",a,b,a+2,b,a+2,b+2,a,b+2);}
