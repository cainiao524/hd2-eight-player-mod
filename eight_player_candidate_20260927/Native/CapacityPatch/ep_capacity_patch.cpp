#include "ep_capacity_patch.h"
#include <windows.h>
#include <atomic>
#include <cstring>
#include <fstream>
#include <sstream>
#include <cstdio>
#include <vector>

namespace {
struct Site { uintptr_t rva; const unsigned char* expected; unsigned char* replacement; size_t size; };
#define SITE(name, rva, ...) static constexpr uintptr_t name##_rva = rva; static const unsigned char name##_old[] = {__VA_ARGS__};
SITE(s108f108,0x108f108,0xc7,0x86,0x90,0x1b,0,0,0x04,0,0,0)
SITE(s10919d1,0x10919d1,0xb9,0x04,0,0,0)
SITE(s1091aa2,0x1091aa2,0x83,0xc1,0x04)
SITE(s1092e78,0x1092e78,0x41,0xb8,0x04,0,0,0)
SITE(s1092ecb,0x1092ecb,0x83,0xf8,0x04)
SITE(s1092ed0,0x1092ed0,0xc7,0x83,0xb0,0x1b,0,0,0x04,0,0,0)
SITE(s1092f31,0x1092f31,0x41,0xb8,0x04,0,0,0)
SITE(s1093a96,0x1093a96,0x83,0xc1,0x04)
SITE(s1093ada,0x1093ada,0x41,0xb8,0x04,0,0,0)
SITE(s1093c91,0x1093c91,0x83,0xf8,0x04)
SITE(s1093c96,0x1093c96,0xc7,0x87,0xb0,0x1b,0,0,0x04,0,0,0)
SITE(s1093cb0,0x1093cb0,0x41,0xb8,0x04,0,0,0)
SITE(s1093d1e,0x1093d1e,0x41,0xb8,0x04,0,0,0)
SITE(s1093fd3,0x1093fd3,0x83,0xf8,0x04)
SITE(s1094105,0x1094105,0x83,0xf8,0x04)
SITE(s10942ac,0x10942ac,0xba,0x04,0,0,0)
SITE(s1094338,0x1094338,0x83,0xf8,0x04)
SITE(s10889e4,0x10889e4,0x83,0xc1,0x04)
SITE(s1088a9a,0x1088a9a,0x83,0xc1,0x04)
SITE(s134dcd4,0x134dcd4,0x83,0xc1,0x04)
SITE(s108c1b5,0x108c1b5,0xb9,0x04,0,0,0)
SITE(s108c1c5,0x108c1c5,0x41,0xb8,0x04,0,0,0)
SITE(s108c2cb,0x108c2cb,0x83,0xf8,0x04)
SITE(s108c393,0x108c393,0x83,0xf8,0x04)
SITE(s108bb62,0x108bb62,0x83,0xf8,0x04)
SITE(s108c3e2,0x108c3e2,0x83,0xf9,0x04)
SITE(s108c4a1,0x108c4a1,0x41,0x83,0xfe,0x04)
SITE(s108c7eb,0x108c7eb,0x83,0xf8,0x04)
SITE(s108c878,0x108c878,0xc7,0x41,0x20,0x04,0,0,0)
SITE(s108c8e7,0x108c8e7,0x41,0xbc,0x04,0,0,0)
SITE(sb90c74,0xb90c74,0x83,0xf9,0x04)
SITE(s1086460,0x1086460,0x42,0x83,0xbc,0x02,0xac,0x63,0x01,0x00,0x04)
SITE(s108c608,0x108c608,0xbd,0x04,0,0,0)
SITE(s108d2d4,0x108d2d4,0xbf,0x04,0,0,0)
SITE(s108d459,0x108d459,0x41,0xbe,0x04,0,0,0)
#undef SITE
#define REP(name) static unsigned char name##_new[sizeof(name##_old)] = {0};
REP(s108f108) REP(s10919d1) REP(s1091aa2) REP(s1092e78) REP(s1092ecb) REP(s1092ed0) REP(s1092f31) REP(s1093a96) REP(s1093ada) REP(s1093c91) REP(s1093c96) REP(s1093cb0) REP(s1093d1e) REP(s1093fd3) REP(s1094105) REP(s10942ac) REP(s1094338) REP(s10889e4) REP(s1088a9a) REP(s134dcd4) REP(s108c1b5) REP(s108c1c5) REP(s108c2cb) REP(s108c393) REP(s108bb62) REP(s108c3e2) REP(s108c4a1) REP(s108c7eb) REP(s108c878) REP(s108c8e7) REP(sb90c74) REP(s1086460) REP(s108c608) REP(s108d2d4) REP(s108d459)
#undef REP
#define ENTRY(name) {name##_rva,name##_old,name##_new,sizeof(name##_old)},
static Site kSites[] = {ENTRY(s108f108)ENTRY(s10919d1)ENTRY(s1091aa2)ENTRY(s1092e78)ENTRY(s1092ecb)ENTRY(s1092ed0)ENTRY(s1092f31)ENTRY(s1093a96)ENTRY(s1093ada)ENTRY(s1093c91)ENTRY(s1093c96)ENTRY(s1093cb0)ENTRY(s1093d1e)ENTRY(s1093fd3)ENTRY(s1094105)ENTRY(s10942ac)ENTRY(s1094338)ENTRY(s10889e4)ENTRY(s1088a9a)ENTRY(s134dcd4)ENTRY(s108c1b5)ENTRY(s108c1c5)ENTRY(s108c2cb)ENTRY(s108c393)ENTRY(s108bb62)ENTRY(s108c3e2)ENTRY(s108c4a1)ENTRY(s108c7eb)ENTRY(s108c878)ENTRY(s108c8e7)ENTRY(sb90c74)ENTRY(s1086460)ENTRY(s108c608)ENTRY(s108d2d4)ENTRY(s108d459)};
#undef ENTRY
std::atomic<unsigned> g_state{0}; // 0 disabled, 1 applied, 2 refused, 3 rolled back
std::atomic<unsigned> g_count{0};
std::atomic<uintptr_t> g_network{0};
std::atomic<uintptr_t> g_session_table{0};
std::atomic<uintptr_t> g_last_session{0};
std::atomic<unsigned> g_ticks{0};
std::vector<std::pair<void*,std::vector<unsigned char>>> g_originals;
const char* name(){return "eight_player_capacity_patch";}
std::string path(){char b[32768]{}; DWORD n=GetEnvironmentVariableA("EP_CAPACITY_PATCH_LOG",b,sizeof(b)); if(n&&n<sizeof(b)) return b; GetTempPathA(sizeof(b),b); return std::string(b)+"hd2_eight_player_capacity_patch.jsonl";}
void log(const char* event,const char* reason="") { std::ofstream o(path(),std::ios::app); if(!o)return; o<<"{\"schema\":\"hd2_capacity_patch_v1\",\"event\":\""<<event<<"\",\"reason\":\""<<reason<<"\",\"state\":"<<g_state.load()<<",\"patched\":"<<g_count.load()<<",\"pid\":"<<GetCurrentProcessId()<<"}\n"; }
void make_replacements(){ for(auto &s:kSites){ std::memcpy(s.replacement,s.expected,s.size); for(size_t i=0;i<s.size;i++) if(s.replacement[i]==4 && (i+1==s.size || s.replacement[i+1]==0)) { s.replacement[i]=8; break; } } }
bool enabled(){char b[8]{}; DWORD n=GetEnvironmentVariableA("EP_ENABLE_CAPACITY_PATCH",b,sizeof(b)); if(n==1&&b[0]=='1') return true; return GetFileAttributesA("bin\\plugins\\eight_player_capacity.enable") != INVALID_FILE_ATTRIBUTES;}
void restore(){ for(auto it=g_originals.rbegin();it!=g_originals.rend();++it){ DWORD old; VirtualProtect(it->first,it->second.size(),PAGE_EXECUTE_READWRITE,&old); std::memcpy(it->first,it->second.data(),it->second.size()); FlushInstructionCache(GetCurrentProcess(),it->first,it->second.size()); VirtualProtect(it->first,it->second.size(),old,&old);} g_originals.clear(); g_count.store(0); g_state.store(3); }
void apply(){
 if(!enabled()){g_state.store(0);log("disabled","EP_ENABLE_CAPACITY_PATCH!=1");return;}
 make_replacements(); HMODULE m=GetModuleHandleA("game.dll"); if(!m){g_state.store(2);log("refused","game.dll_not_loaded");return;} auto base=reinterpret_cast<unsigned char*>(m);
 for(auto &s:kSites){ if(std::memcmp(base+s.rva,s.expected,s.size)!=0){g_state.store(2);log("refused","site_fingerprint_mismatch"); return;} }
 for(auto &s:kSites){ void* p=base+s.rva; DWORD old; g_originals.emplace_back(p,std::vector<unsigned char>(s.expected,s.expected+s.size)); bool wrote=false; if(VirtualProtect(p,s.size,PAGE_EXECUTE_READWRITE,&old)){ std::memcpy(p,s.replacement,s.size); FlushInstructionCache(GetCurrentProcess(),p,s.size); VirtualProtect(p,s.size,old,&old); wrote=true; } else { SIZE_T done=0; wrote=WriteProcessMemory(GetCurrentProcess(),p,s.replacement,s.size,&done)!=FALSE && done==s.size; if(wrote) FlushInstructionCache(GetCurrentProcess(),p,s.size); } if(!wrote){ char why[128]; std::snprintf(why,sizeof(why),"write_failed_%lu_rva_%llx",(unsigned long)GetLastError(),(unsigned long long)s.rva); g_state.store(2);log("refused",why); restore(); return;} g_count.fetch_add(1); }
 g_state.store(1); log("applied","fixed_build_sites_35");
}
void loaded(ep_cap_get_api_fn get){ log("loaded"); if(get){ auto c=reinterpret_cast<void**>(get(31)); if(c){ g_network.store(reinterpret_cast<uintptr_t>(c[7])); g_session_table.store(reinterpret_cast<uintptr_t>(c[8])); } } }
void observe_session(){
 auto n=g_network.load(); if(!n)return;
 using get_session_fn=void*(*)();
 auto get_session=*reinterpret_cast<get_session_fn*>(n+sizeof(void*));
 if(!get_session)return;
 // The fixed-build Network wrapper is a getter at +0x34fdf0.  The HD2
 // GameSession table is not the public SDK layout, so peer()/num_peers() are
 // deliberately not called until their wrapper and callee contracts are bound.
 const unsigned char expected[] = {0x48,0x8b,0x05,0x81,0x04,0x6c,0x01,0x48,0x8b,0x80,0xa8,0,0,0,0xc3};
 MEMORY_BASIC_INFORMATION mbi{};
 if(VirtualQuery(reinterpret_cast<const void*>(get_session),&mbi,sizeof(mbi))==0 ||
    mbi.State!=MEM_COMMIT || mbi.Protect==PAGE_NOACCESS ||
    mbi.RegionSize<sizeof(expected) || std::memcmp(reinterpret_cast<const void*>(get_session),expected,sizeof(expected))!=0) return;
 void* session=get_session();
 auto old_s=g_last_session.exchange(reinterpret_cast<uintptr_t>(session));
 if(old_s!=reinterpret_cast<uintptr_t>(session)){
  std::ofstream o(path(),std::ios::app);
  if(o){
   o<<"{\"schema\":\"hd2_capacity_patch_v2\",\"event\":\"session_pointer_observe\",\"session\":\"0x"<<std::hex<<reinterpret_cast<uintptr_t>(session)<<"\",\"getter_code_pinned\":true,\"peer_state_read\":false,\"pid\":"<<std::dec<<GetCurrentProcessId()<<"}\n";
  }
 }
}
void setup_game(ep_cap_get_api_fn get){ if(get){ auto c=reinterpret_cast<void**>(get(31)); if(c){ g_network.store(reinterpret_cast<uintptr_t>(c[7])); g_session_table.store(reinterpret_cast<uintptr_t>(c[8])); } } if(g_state.load()==0 || g_state.load()==2) apply(); observe_session(); }
void update_game(float){ if((++g_ticks%60u)==0u){ if(g_state.load()==0 || g_state.load()==2) apply(); observe_session(); } }
void unloaded(){ if(g_state.load()==1) restore(); else log("unloaded"); }
ep_cap_plugin_api& api(){ static ep_cap_plugin_api a{}; static bool init=false; if(!init){a.get_name=&name;a.loaded=&loaded;a.unloaded=&unloaded;a.setup_game=&setup_game;a.update_game=&update_game;init=true;} return a;}
}
EP_CAP_EXPORT void* get_plugin_api(unsigned id){return id==EP_CAP_PLUGIN_API_ID?&api():nullptr;}
EP_CAP_EXPORT unsigned ep_capacity_patch_state(){return g_state.load();}
EP_CAP_EXPORT unsigned ep_capacity_patch_count(){return g_count.load();}
