/* Native property producers -> actual backend -> native receivers -> actual
 * loader consumers. All memory images and identity tickets remain synthetic. */
#include "native_fixture.h"
int main(int argc, char** argv)
{
    CHECK(argc == 17);
    strcpy(g_build,"25480438"); g_modCount=1; g_mods[0].loaded=1;
    CHECK(ApiSubscribe(&g_mods[0],HF_ON_PLAYER_SPAWN,Heard,NULL,0));
    EpNativeRosterSource source={NULL,Begin,ReadMemory,End};
    EpHfRosterProvider provider={sizeof provider,1,8,0,&source,ep_native_roster_read};
    for(unsigned node=0;node<8;node++)
    {
        LoadFixture(argv[1+node*2]);
        view.epoch=100+node; view.build=25480438; view.ticket_count=8;
        for(unsigned peer=0;peer<8;peer++)
            view.tickets[peer]=(EpNativeTicket){100+peer,100+node,(node+1)*256+1+8*peer,(3*peer+2)%8,10+peer,0};
        EpHfRosterSnapshot out;
        CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH);
        uint64_t lease=EpRosterBind(&g_mods[0],&provider); CHECK(lease!=0);
        CHECK(EpRosterRead(view.game,&out)==-1);
        PollPlayers(view.game); CHECK(spawns==node*8);
        LoadFixture(argv[2+node*2]);
        CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==8 && readBytes==2024);
        for(unsigned ordinal=0;ordinal<8;ordinal++)
        {
            unsigned peer=ordinal;
            if(ordinal==(node+1)%8) peer=(node+2)%8;
            else if(ordinal==(node+2)%8) peer=(node+1)%8;
            CHECK(out.players[ordinal].peer==100+peer && out.players[ordinal].player==(node+1)*256+1+8*peer &&
                  out.players[ordinal].network_index==(3*peer+2)%8 && out.players[ordinal].network_id==0x7FFF &&
                  out.players[ordinal].generation==10+peer && out.players[ordinal].local==(peer==node));
        }
        CHECK(EpRosterRead(view.game,&out)==8 && out.binding==lease);
        PollPlayers(view.game); CHECK(g_playerCount==8 && spawns==(node+1)*8);
        PollPlayers(view.game); CHECK(spawns==(node+1)*8);
        CHECK(ActPlayerCount(view.game)==8);
        uint32_t saved=NativeU32(regions[1].data+0x58C);
        Write32(1,0x58C,8); CHECK(EpRosterRead(view.game,&out)==-1);
        PollPlayers(view.game); CHECK(spawns==(node+1)*8); Write32(1,0x58C,saved);
        CHECK(EpRosterUnbind(&g_mods[0],lease));
    }
    CHECK(acquired==released);
    printf("native roster sync: %u checks passed; eight synthetic recipients, real patched consumers\n",checks);
    return 0;
}
