#include "native_fixture.h"
int main(int argc, char** argv)
{
    CHECK(argc == 4); LoadFixture(argv[1]);
    view.epoch=42; view.build=25480438; view.ticket_count=8;
    for (unsigned i=0;i<8;i++) view.tickets[i]=(EpNativeTicket){100+i,42,1+8*i,(3*i+2)%8,10+i,0};
    EpNativeRosterSource source={NULL,Begin,ReadMemory,End}; EpHfRosterSnapshot out;
    CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==8 && out.capacity==8);
    CHECK(readBytes == 2024);
    for(unsigned i=0;i<8;i++) CHECK(out.players[i].player==1+8*i && out.players[i].peer==100+i &&
        out.players[i].network_index==(3*i+2)%8 && out.players[i].network_id==0x1000+i &&
        out.players[i].generation==10+i && out.players[i].local==(i==7));
    unsigned successfulReads=reads;
    for(unsigned i=1;i<=successfulReads;i++) { failAt=i; CHECK(Snapshot(&source,&out)==EP_NATIVE_READ_FAILED); }
    failAt=0; unavailable=1; CHECK(Snapshot(&source,&out)==EP_NATIVE_UNAVAILABLE); unavailable=0;
    changeBinding=1; CHECK(Snapshot(&source,&out)==EP_NATIVE_BINDING_CHANGED); changeBinding=0;
    view.build=1; CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); view.build=25480438;
    view.storage++; CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); view.storage--;
    Write32(0,0x80,9); CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); Write32(0,0x80,8);
    Write32(0,0x84,1); Write32(0,0x88,1); CHECK(Snapshot(&source,&out)==EP_NATIVE_PENDING);
    Write32(0,0x84,8); Write32(0,0x88,9); CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); Write32(0,0x88,8);
    Write32(0,0xD8,16); CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); Write32(0,0xD8,8);
    uint32_t saved=NativeU32(regions[2].data+12); Write32(2,12,7);
    CHECK(Snapshot(&source,&out)==EP_NATIVE_MAP_MISMATCH); Write32(2,12,saved);
    view.tickets[7].network_index=0; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.tickets[7].network_index=7;
    view.tickets[7].epoch=41; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.tickets[7].epoch=42;
    view.tickets[7].generation=0; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.tickets[7].generation=17;
    view.ticket_count=7; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.ticket_count=8;
    Write32(1,0x580+7*0x20+0xC,8); CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH);
    Write32(1,0x580+7*0x20+0xC,7);
    /* Real private engine provider consumes the emitted storage, not a prebuilt EpHf snapshot. */
    strcpy(g_build,"25480438"); g_modCount=1; g_mods[0].loaded=1;
    EpHfRosterProvider provider={sizeof provider,1,8,0,&source,ep_native_roster_read};
    uint64_t lease=EpRosterBind(&g_mods[0],&provider); CHECK(lease!=0);
    CHECK(EpRosterRead(view.game,&out)==8 && out.binding==lease && out.players[7].network_index==7);
    CHECK(ApiSubscribe(&g_mods[0],HF_ON_PLAYER_SPAWN,Heard,NULL,0));
    PollPlayers(view.game); CHECK(spawns==8 && g_playerCount==8);
    PollPlayers(view.game); CHECK(spawns==8);
    view.tickets[7].generation++; PollPlayers(view.game); CHECK(spawns==9);
    unavailable=1; CHECK(EpRosterRead(view.game,&out)==-1); PollPlayers(view.game); CHECK(spawns==9); unavailable=0;
    CHECK(ActPlayerCount(view.game)==8);
    LoadFixture(argv[2]);
    CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==7);
    CHECK(out.players[4].peer==107 && out.players[4].network_index==7 && out.players[4].local);
    for(unsigned i=0;i<out.count;i++) CHECK(out.players[i].peer!=104);
    PollPlayers(view.game); CHECK(g_playerCount==7 && spawns==9);
    LoadFixture(argv[3]); view.tickets[4].generation++;
    CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==8);
    CHECK(out.players[7].peer==104 && out.players[7].network_index==6 && out.players[7].generation==15);
    CHECK(out.players[4].peer==107 && out.players[4].network_index==7 && out.players[4].local);
    PollPlayers(view.game); CHECK(g_playerCount==8 && spawns==10);
    CHECK(EpRosterUnbind(&g_mods[0],lease)); CHECK(acquired==released);
    printf("native roster source: %u checks passed; emitted native insert storage to real loader consumers\n",checks);
    return 0;
}
