/* Windows unwinds synthetic contexts. No candidate/game instruction executes
 * natively: code is stored in PAGE_READWRITE (non-executable) memory. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void take(FILE* f, void* out, size_t n) {
    if (fread(out, 1, n, f) != n) { fputs("truncated fixture\n", stderr); exit(2); }
}
static uint32_t u32(FILE* f) { uint32_t v; take(f, &v, 4); return v; }
static void check(int ok, const char* why) {
    if (!ok) { fprintf(stderr, "%s\n", why); exit(3); }
}
static void registers(CONTEXT* c, const uint64_t r[8]) {
    c->Rbx=r[0]; c->Rbp=r[1]; c->Rsi=r[2]; c->Rdi=r[3];
    c->R12=r[4]; c->R13=r[5]; c->R14=r[6]; c->R15=r[7];
}
static int same(const CONTEXT* c, const uint64_t r[8]) {
    return c->Rbx==r[0] && c->Rbp==r[1] && c->Rsi==r[2] && c->Rdi==r[3] &&
           c->R12==r[4] && c->R13==r[5] && c->R14==r[6] && c->R15==r[7];
}
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    FILE* f = fopen(argv[1], "rb"); check(f != NULL, "fixture missing");
    char magic[8]; take(f, magic, 8); check(memcmp(magic,"EPUWDV1\0",8)==0, "wrong fixture");
    uint32_t variants = u32(f), fixed=0, baseline=0, expected_failures=0;
    check(variants == 2, "expected legacy and corrected variants");
    for (uint32_t v=0; v<variants; ++v) {
        uint32_t size=u32(f), code_size=u32(f), table_offset=u32(f), count=u32(f);
        check(size<4096 && code_size<size && table_offset+sizeof(RUNTIME_FUNCTION)==size && count<10000, "invalid image bounds");
        uint8_t* image=VirtualAlloc(NULL,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        check(image!=NULL,"allocation failed"); take(f,image,size);
        PRUNTIME_FUNCTION table=(PRUNTIME_FUNCTION)(image+table_offset);
        check(table->BeginAddress==0 && table->EndAddress==code_size && table->UnwindData+24<=table_offset,"invalid function entry");
        check(RtlAddFunctionTable(table,1,(DWORD64)image),"function table registration failed");
        uint64_t expected[8], return_pc; take(f,expected,sizeof expected); take(f,&return_pc,8);
        for (uint32_t k=0; k<count; ++k) {
            uint32_t pc=u32(f); int32_t delta=(int32_t)u32(f); uint32_t should_fail=u32(f);
            check(pc<code_size && delta>=-128 && delta<=0 && should_fail<=1 && (v==0 || !should_fail),"invalid context bounds");
            uint64_t values[8]; take(f,values,sizeof values);
            _Alignas(16) uint8_t stack[512]={0}; uint8_t* entry=stack+264;
            take(f,entry-128,256);
            CONTEXT c={0}; c.ContextFlags=CONTEXT_FULL; registers(&c,values);
            c.Rip=(DWORD64)image+pc; c.Rsp=(DWORD64)entry+delta;
            DWORD64 base=0, frame=0; PVOID data=NULL;
            PRUNTIME_FUNCTION found=RtlLookupFunctionEntry(c.Rip,&base,NULL);
            check(found==table && base==(DWORD64)image,"lookup did not find owned table");
            PEXCEPTION_ROUTINE handler=RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,found,&c,&data,&frame,NULL);
            int ok=handler==NULL && c.Rip==return_pc && c.Rsp==(DWORD64)entry+8 && same(&c,expected);
            if (ok == (int)should_fail) {
                fprintf(stderr,"variant=%u case=%u pc=0x%x expected_failure=%u rsp_delta=%lld rip=%llx expected=%llx regs=%d\n",
                        v,k,pc,should_fail,(long long)(c.Rsp-(DWORD64)entry),(unsigned long long)c.Rip,
                        (unsigned long long)return_pc,same(&c,expected));
                return 4;
            }
            if (should_fail) expected_failures++;
            else if (v==0) baseline++;
            else fixed++;
        }
        check(RtlDeleteFunctionTable(table),"table unregister failed");
        DWORD64 gone=0; check(RtlLookupFunctionEntry((DWORD64)image+24,&gone,NULL)==NULL,"stale function table after unregister");
        check(VirtualFree(image,0,MEM_RELEASE),"image release failed");
    }
    check(fgetc(f)==EOF,"trailing fixture data"); fclose(f);
    check(expected_failures>0 && fixed>0,"missing negative control or corrected contexts");
    printf("{\"passed\":true,\"windows_unwind_contexts\":%u,\"legacy_valid_contexts\":%u,\"legacy_rejection_failures_reproduced\":%u,\"game_access\":false}\n",
           fixed,baseline,expected_failures);
    return 0;
}
