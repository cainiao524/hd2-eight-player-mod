#include "native_fixture.h"
int main(int argc,char** argv)
{
    CHECK(argc==4);
    const unsigned order[3][8]={{0,1,2,3,4,5,6,7},{0,1,7,3,4,5,6,2},{7,1,0,3,4,5,6,2}};
    const unsigned prefix[3]={2,3,2};
    view.epoch=42;view.build=25480438;view.ticket_count=8;
    for(unsigned i=0;i<8;i++) view.tickets[i]=(EpNativeTicket){100+i,42,11+8*i,(3*i+2)%8,10+i,0};
    EpNativeRosterSource source={NULL,Begin,ReadMemory,End};EpHfRosterSnapshot out;
    strcpy(g_build,"25480438");g_modCount=1;g_mods[0].loaded=1;
    EpHfRosterProvider provider={sizeof provider,1,8,0,&source,ep_native_roster_read};
    uint64_t lease=EpRosterBind(&g_mods[0],&provider);CHECK(lease!=0);
    CHECK(ApiSubscribe(&g_mods[0],HF_ON_PLAYER_SPAWN,Heard,NULL,0));
    for(unsigned phase=0;phase<3;phase++) {
        LoadFixture(argv[phase+1]);
        CHECK(NativeU32(regions[0].data+0x88)==prefix[phase]);
        CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==8 && out.capacity==8);
        CHECK(readBytes==2024);
        for(unsigned i=0;i<8;i++) {
            unsigned peer=order[phase][i];
            CHECK(out.players[i].peer==100+peer && out.players[i].player==11+8*peer &&
                  out.players[i].network_index==(3*peer+2)%8 && out.players[i].network_id==0x1000+peer &&
                  out.players[i].generation==10+peer && out.players[i].local==(peer==7));
        }
        CHECK(EpRosterRead(view.game,&out)==8 && out.binding==lease);
        PollPlayers(view.game);CHECK(g_playerCount==8 && spawns==8);
        CHECK(ActPlayerCount(view.game)==8);
        Write32(0,0x88,9);CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT);Write32(0,0x88,prefix[phase]);
    }
    CHECK(EpRosterUnbind(&g_mods[0],lease));CHECK(acquired==released);
    printf("native classification source: %u checks passed; emitted classification storage to real loader consumers\n",checks);
    return 0;
}
