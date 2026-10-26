/* Synthetic, non-executable images only. Never opens a game process. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void check(int ok,const char* why) { if (!ok) { fputs(why,stderr);exit(3); } }
static void take(FILE* f,void* p,size_t z) { check(fread(p,1,z,f)==z,"truncated fixture"); }
static uint32_t u32(FILE* f) { uint32_t v;take(f,&v,4);return v; }
static uint64_t relocate(uint64_t v,uint8_t* image,uint32_t size,uint8_t* entry) {
    if (v>=UINT64_C(0x100000000) && v<UINT64_C(0x100000000)+size) return (uint64_t)image+v-UINT64_C(0x100000000);
    if (v>=UINT64_C(0x1fffffe00) && v<UINT64_C(0x200000080)) return (uint64_t)entry+v-UINT64_C(0x200000000);
    return v;
}
int main(int argc,char** argv) {
    if (argc!=2) return 2;
    FILE* f=fopen(argv[1],"rb");check(f!=NULL,"fixture missing");char magic[8];take(f,magic,8);check(!memcmp(magic,"EPRDRW1\0",8),"fixture magic");
    uint32_t variants=u32(f),passed=0,negative=0;check(variants==4,"fixture variants");
    for (uint32_t v=0;v<variants;v++) {
        uint32_t size=u32(f),table=u32(f),count=u32(f),contexts=u32(f);
        check(size<16384 && count<16 && contexts<10000 && table+12*count==size,"fixture bounds");
        uint8_t* image=VirtualAlloc(NULL,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);check(image!=NULL,"allocation");take(f,image,size);
        RUNTIME_FUNCTION* rows=(RUNTIME_FUNCTION*)(image+table);
        for (uint32_t i=0;i<count;i++) check(rows[i].BeginAddress<rows[i].EndAddress && rows[i].EndAddress<=table && rows[i].UnwindData<table && (!i || rows[i-1].EndAddress<=rows[i].BeginAddress),"function bounds");
        check(RtlAddFunctionTable(rows,count,(DWORD64)image),"register table");uint64_t expected[9];take(f,expected,sizeof expected);
        for (uint32_t j=0;j<contexts;j++) {
            uint32_t pc=u32(f);int32_t delta=(int32_t)u32(f);uint32_t fail=u32(f),levels=u32(f);uint64_t regs[8];take(f,regs,sizeof regs);
            check(pc<table && delta>=-512 && delta<=0 && fail<=1 && levels>=1 && levels<=2,"context bounds");
            _Alignas(16) uint8_t stack[1024]={0};uint8_t* entry=stack+776;take(f,entry-512,640);
            for (unsigned k=0;k<640;k+=8) { uint64_t x;memcpy(&x,entry-512+k,8);x=relocate(x,image,size,entry);memcpy(entry-512+k,&x,8); }
            for (unsigned k=0;k<8;k++) regs[k]=relocate(regs[k],image,size,entry);
            CONTEXT c={0};c.ContextFlags=CONTEXT_FULL;c.Rip=(DWORD64)image+pc;c.Rsp=(DWORD64)entry+delta;
            c.Rbx=regs[0];c.Rbp=regs[1];c.Rsi=regs[2];c.Rdi=regs[3];c.R12=regs[4];c.R13=regs[5];c.R14=regs[6];c.R15=regs[7];
            int ok=1;
            for (uint32_t k=0;k<levels;k++) {
                DWORD64 base=0,frame=0;PVOID data=NULL;PRUNTIME_FUNCTION row=RtlLookupFunctionEntry(c.Rip,&base,NULL);
                check(row>=rows && row<rows+count && base==(DWORD64)image,"lookup missed owned frame");
                ok=ok && RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&data,&frame,NULL)==NULL;
            }
            uint64_t actual[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
            ok=ok && !memcmp(actual,expected,sizeof actual) && c.Rip==expected[8] && c.Rsp==(DWORD64)entry+8;
            if (ok==(int)fail) { fprintf(stderr,"variant=%u case=%u pc=%x delta=%d levels=%u fail=%u finalrsp=%lld\n",v,j,pc,delta,levels,fail,(long long)(c.Rsp-(DWORD64)entry));return 4; }
            if (fail)negative++;else passed++;
        }
        check(RtlDeleteFunctionTable(rows),"remove table");VirtualFree(image,0,MEM_RELEASE);
    }
    check(fgetc(f)==EOF,"trailing fixture");fclose(f);check(negative==2,"missing negative controls");
    printf("{\"passed\":true,\"windows_unwind_contexts\":%u,\"negative_controls_rejected\":%u,\"game_access\":false}\n",passed,negative);return 0;
}
