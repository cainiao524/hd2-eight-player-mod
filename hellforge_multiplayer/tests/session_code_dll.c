#include "session_code_dll.h"
#include "../mod/src/ep_session_code.cpp"
__declspec(dllexport) const SessionCodeTestApi* session_code_test_api(void)
{
    static const SessionCodeTestApi api={ep_session_code_reserve,ep_session_code_seal,
        ep_session_code_info,ep_session_code_publish,ep_session_code_discard};
    return &api;
}
