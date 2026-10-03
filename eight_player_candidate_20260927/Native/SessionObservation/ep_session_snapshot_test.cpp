#include "ep_session_snapshot.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

struct Image {
    uintptr_t base = 0x10000000;
    std::vector<uint8_t> bytes = std::vector<uint8_t>(0x3000000);
    bool read(uintptr_t address, void* out, size_t size) {
        if (address < base || address - base > bytes.size() || size > bytes.size() - (address-base)) return false;
        std::memcpy(out, bytes.data() + (address-base), size); return true;
    }
    template<class T> void put(uintptr_t address, const T& value) {
        assert(address >= base && address-base+sizeof(T) <= bytes.size());
        std::memcpy(bytes.data()+(address-base), &value, sizeof(T));
    }
    void put_bytes(uintptr_t address, const uint8_t* value, size_t size) {
        assert(address >= base && address-base+size <= bytes.size());
        std::memcpy(bytes.data()+(address-base), value, size);
    }
};

int main() {
    Image image;
    const uintptr_t b=image.base, root=b+0x200000, session=b+0x210000, data=b+0x220000;
    uint16_t mz=0x5a4d, machine=0x8664, magic=0x20b; uint32_t pe=0x1000, sig=0x4550, ts=1790149348u, image_size=60719104u;
    image.put(b+0,mz); image.put(b+0x3c,pe); image.put(b+pe,sig); image.put(b+pe+4,machine); image.put(b+pe+8,ts); image.put(b+pe+24,magic); image.put(b+pe+24+56,image_size);
    const uint8_t getter[]={0x48,0x8b,0x05,0x81,0x04,0x6c,0x01,0x48,0x8b,0x80,0xa8,0,0,0,0xc3};
    const uint8_t count[]={0x8b,0x81,0x38,0x01,0,0,0xc3};
    const uint8_t peer[]={0x8b,0xc2,0x48,0x8d,0x14,0x40,0x48,0x8b,0x81,0x40,0x01,0,0,0x48,0x03,0xd2,0x48,0x8b,0x04,0xd0,0xc3};
    const uint8_t host[]={0x48,0x8b,0x81,0x30,0x01,0,0,0xc3};
    image.put_bytes(b+0x34fdf0,getter,sizeof(getter)); image.put_bytes(b+0x292be0,count,sizeof(count)); image.put_bytes(b+0x292bf0,peer,sizeof(peer)); image.put_bytes(b+0x292cc0,host,sizeof(host));
    uintptr_t vtable=b+0x1675b70, fn_count=b+0x292be0, fn_peer=b+0x292bf0, fn_host=b+0x292cc0;
    image.put(b+0x1a10278,root); image.put(root+0xa8,session); image.put(session,vtable); image.put(vtable+0x70,fn_count); image.put(vtable+0x78,fn_peer); image.put(vtable+0x98,fn_host);
    uint64_t host_id=0x1234; uint32_t count_value=2; uint32_t padding=0; image.put(session+0x130,host_id); image.put(session+0x138,count_value); image.put(session+0x13c,padding); image.put(session+0x140,data);
    uint64_t id0=0x1111,id1=0x2222; image.put(data,id0); image.put(data+48,id1);
    auto ok=ep_session::capture(b,[&](uintptr_t address,void* out,size_t size){return image.read(address,out,size);});
    assert(ok.status==std::string("stable_bounded_records_not_player_proof")); assert(ok.record_count==2 && ok.record_ids[0]==id0 && ok.record_ids[1]==id1);
    image.put(session+0x138,uint32_t(9)); auto rejected=ep_session::capture(b,[&](uintptr_t address,void* out,size_t size){return image.read(address,out,size);});
    assert(rejected.status==std::string("count_exceeds_observation_bound"));
    image.put(session+0x138,count_value); image.put_bytes(b+0x292be0,count+1,sizeof(count)-1);
    auto mismatch=ep_session::capture(b,[&](uintptr_t address,void* out,size_t size){return image.read(address,out,size);}); assert(mismatch.status==std::string("code_identity_refused"));
    std::cout << "session_snapshot_synthetic_passed\n";
}
