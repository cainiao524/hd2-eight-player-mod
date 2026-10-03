#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>
struct Site { std::vector<uint8_t> oldb,newb; };
static std::vector<uint8_t> replace(std::vector<uint8_t> in){ bool changed=false; for(size_t i=0;i<in.size();++i){ if(in[i]==4 && (i+1==in.size() || in[i+1]==0)){in[i]=8; changed=true; break;} } assert(changed); return in; }
int main(){ std::vector<Site> s={{{0xc7,0x86,0x90,0x1b,0,0,0x04,0,0,0},{}},{{0xb9,4,0,0,0},{}},{{0x41,0xb8,4,0,0,0},{}},{{0x83,0xf8,4},{}},{{0xba,4,0,0,0},{}}}; for(auto &x:s)x.newb=replace(x.oldb); assert(s[0].newb[6]==8); assert(s[1].newb[1]==8); assert(s[2].newb[2]==8); assert(s[3].newb[2]==8); assert(s[4].newb[1]==8); std::cout<<"capacity_patch_synthetic_passed\n"; }
