#define EP_REGISTRY 1
#define EP_CONTEXT_LIMIT 200000u
/* Wide stack plus XMM6 contexts for the saved departure frame. */
/* Windows unwinds synthetic contexts. No candidate/game instruction executes
 * natively: code is stored in PAGE_READWRITE (non-executable) memory. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef EP_CONTEXT_LIMIT
#define EP_CONTEXT_LIMIT 10000u
#endif

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
    char magic[8]; take(f, magic, 8); check(memcmp(magic,"EPUWDX1\0",8)==0, "wrong fixture");
    uint32_t variants = u32(f), fixed=0, baseline=0, expected_failures=0;
    check(variants == 4, "expected three independent negative controls and corrected image");
    for (uint32_t v=0; v<variants; ++v) {
        uint32_t size=u32(f), code_size=u32(f), table_offset=u32(f), count=u32(f);
        check(size<4096 && code_size<size && table_offset<size && (size-table_offset)%sizeof(RUNTIME_FUNCTION)==0 && count<EP_CONTEXT_LIMIT, "invalid image bounds");
        uint32_t functions=(size-table_offset)/sizeof(RUNTIME_FUNCTION);
#if defined(EP_REGISTRY)
        check(functions>=3 && functions<=15,"invalid registry function count");
#else
        check(functions>=1 && functions<=3,"invalid function count");
#endif
        uint8_t* image=VirtualAlloc(NULL,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        check(image!=NULL,"allocation failed"); take(f,image,size);
        PRUNTIME_FUNCTION table=(PRUNTIME_FUNCTION)(image+table_offset);
        check(table->BeginAddress==0 && table[functions-1].EndAddress==code_size && table[functions-1].UnwindData<=table_offset && table_offset-table[functions-1].UnwindData>=4,"invalid function entry");
#if defined(EP_REGISTRY)
        for (uint32_t index=0;index<functions;index++) {
            uint32_t at=table[index].UnwindData;
            check(at>=code_size && at<=table_offset-4,"invalid registry unwind position");
            uint8_t* uw=image+at;uint32_t body=4u+((uw[2]+1u)&~1u)*2u;
            check((uw[0]==1 || uw[0]==33) && uw[3]==0 && body<=table_offset-at,"invalid registry unwind header");
            if (uw[0]==33) {
                check(body+12<=table_offset-at,"truncated registry chain");int found=0;
                for (uint32_t parent=0;parent<index;parent++) if (!memcmp(uw+body,table+parent,12)) found=1;
                check(found,"registry chain is not a prior owned row");
            }
        }
#else
        uint8_t* unwind=image+table[functions-1].UnwindData;
        check(unwind[0]==1 && unwind[3]==0 && 4u+((unwind[2]+1u)&~1u)*2u<=table_offset-table[functions-1].UnwindData,"invalid unwind extent");
#endif
        for (uint32_t index=1;index<functions;index++) check(table[index-1].EndAddress==table[index].BeginAddress,"invalid contiguous functions");
#if !defined(EP_REGISTRY)
        if (functions>=2) {
            check(table[0].EndAddress>0,"invalid leaf extent");
            check(table[0].UnwindData>=code_size && table[0].UnwindData<=size-4,"invalid preflight unwind location");
#if defined(EP_ROSTER_GATES)
            const uint8_t prefix[]={1,9,7,0,9,0x70,8,0x60,7,0x30,6,2,4,2,2,2,1,2,0,0};
            check(!memcmp(image+table[0].UnwindData,"\1\0\0\0",4) ||
                  (size-table[0].UnwindData>=sizeof(prefix) && !memcmp(image+table[0].UnwindData,prefix,sizeof(prefix))),"unknown prefix unwind");
#elif defined(EP_STACK_PREFLIGHT)
            const uint8_t prefix[]={1,9,7,0,9,0x70,8,0x60,7,0x30,6,2,4,2,2,2,1,2,0,0};
            check(size-table[0].UnwindData>=sizeof(prefix) && !memcmp(image+table[0].UnwindData,prefix,sizeof(prefix)),"invalid saved-argument preflight");
#else
            check(!memcmp(image+table[0].UnwindData,"\1\0\0\0",4),"invalid leaf unwind");
#endif
        }
#endif
        check(RtlAddFunctionTable(table,functions,(DWORD64)image),"function table registration failed");
        uint64_t expected[8], return_pc; take(f,expected,sizeof expected); take(f,&return_pc,8);
        M128A expected_xmm;take(f,&expected_xmm,16);
        for (uint32_t k=0; k<count; ++k) {
            uint32_t pc=u32(f); int32_t delta=(int32_t)u32(f); uint32_t should_fail=u32(f);
            check(pc<code_size && delta>=-256 && delta<=0 && should_fail<=1 && (v+1<variants || !should_fail),"invalid context bounds");
            uint64_t values[8]; take(f,values,sizeof values);
            M128A xmm;take(f,&xmm,16);
            _Alignas(16) uint8_t stack[768]={0}; uint8_t* entry=stack+520;
            take(f,entry-256,384);
            CONTEXT c={0}; c.ContextFlags=CONTEXT_FULL; registers(&c,values); c.Xmm6=xmm;
            c.Rip=(DWORD64)image+pc; c.Rsp=(DWORD64)entry+delta;
            DWORD64 base=0, frame=0; PVOID data=NULL;
            PRUNTIME_FUNCTION found=RtlLookupFunctionEntry(c.Rip,&base,NULL);
            uint32_t row=0;while (row+1<functions && pc>=table[row+1].BeginAddress) row++;
            check(found==table+row && base==(DWORD64)image,"lookup did not find owned table");
            PEXCEPTION_ROUTINE handler=RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,found,&c,&data,&frame,NULL);
            int ok=handler==NULL && c.Rip==return_pc && c.Rsp==(DWORD64)entry+8 && same(&c,expected) && !memcmp(&c.Xmm6,&expected_xmm,16);
            if (ok == (int)should_fail) {
                fprintf(stderr,"variant=%u case=%u pc=0x%x expected_failure=%u rsp_delta=%lld rip=%llx expected=%llx regs=%d\n",
                        v,k,pc,should_fail,(long long)(c.Rsp-(DWORD64)entry),(unsigned long long)c.Rip,
                        (unsigned long long)return_pc,same(&c,expected));
                const uint64_t actual[8]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
                for(unsigned j=0;j<8;j++) if(actual[j]!=expected[j])
                    fprintf(stderr,"nonvolatile[%u]=%llx expected=%llx\n",j,(unsigned long long)actual[j],(unsigned long long)expected[j]);
                fprintf(stderr,"xmm6_matches=%d\n",!memcmp(&c.Xmm6,&expected_xmm,16));
                return 4;
            }
            if (should_fail) expected_failures++;
            else if (v+1<variants) baseline++;
            else fixed++;
        }
        check(RtlDeleteFunctionTable(table),"table unregister failed");
        DWORD64 gone=0; check(RtlLookupFunctionEntry((DWORD64)image+24,&gone,NULL)==NULL,"stale function table after unregister");
        check(VirtualFree(image,0,MEM_RELEASE),"image release failed");
    }
    check(fgetc(f)==EOF,"trailing fixture data"); fclose(f);
    check(expected_failures>0 && fixed>0,"missing negative control or corrected contexts");
    printf("{\"passed\":true,\"windows_unwind_contexts\":%u,\"legacy_valid_contexts\":%u,\"negative_controls_rejected\":%u,\"game_access\":false}\n",
           fixed,baseline,expected_failures);
    return 0;
}
