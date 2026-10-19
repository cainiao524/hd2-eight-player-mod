"""Offline tests for the Lua/native capacity runtime boundary.

The fixture is entirely Lua state. It does not load a DLL, access HD2, or
pretend that a synthetic provider is a live multiplayer implementation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".test-deps"))
from lupa.luajit21 import LuaRuntime  # type: ignore


CONTRACT = (ROOT / "Source/player_capacity_contract.lua").read_text(encoding="utf-8")
RUNTIME = (ROOT / "Source/player_capacity_runtime.lua").read_text(encoding="utf-8")


def run_fixture(result_name: str) -> dict:
    script = """
package.preload["mods/cainiao/hd2_capacity_contract"] = function()
""" + CONTRACT + """
end
local runtime_module = (function()
""" + RUNTIME + """
end)()
local contract = require("mods/cainiao/hd2_capacity_contract")
local state, created = contract.new_state({
    authority="host", verified_capacity=8, configured_max_players=8,
    peer_capacity=8, roster_capacity=8, entity_capacity=8,
    resource_capacity=8, network_capacity=8
})
assert(created.accepted)
local logs = {}
local native = {
    snapshot = function()
        local snapshot = contract.snapshot(state)
        return snapshot
    end,
    submit = function(current, desired)
        return {accepted=true, reason="pending", desired=desired.max_players}
    end
}
local runtime = {
    mod = function(name)
        assert(name == "mods/cainiao/hd2_capacity_menu")
        return {log=function(_, message) logs[#logs + 1] = message end}
    end
}
local service, service_error = runtime_module.new(native, runtime)
assert(service, service_error and service_error.reason)
local result = {}
result.valid = service.submit_config({
    preset="8 Players", max_players=8, allow_join_in_progress=true,
    require_same_mod_version=true, apply_mode="next_lobby"
})
result.invalid_flags = service.submit_config({
    preset="8 Players", max_players=8, allow_join_in_progress=1,
    require_same_mod_version=true, apply_mode="next_lobby"
})
result.invalid_mode = service.submit_config({
    preset="8 Players", max_players=8, allow_join_in_progress=true,
    require_same_mod_version=true, apply_mode="immediate"
})
result.logs = #logs
return result
"""
    runtime = LuaRuntime(unpack_returned_tuples=True)
    result = runtime.execute(script)
    return {key: value for key, value in result.items()}


class CapacityRuntimeTests(unittest.TestCase):
    def test_valid_request_is_forwarded_and_invalid_fields_fail_closed(self):
        result = run_fixture("valid")
        self.assertTrue(result["valid"]["accepted"])
        self.assertEqual(result["valid"]["reason"], "pending")
        self.assertFalse(result["invalid_flags"]["accepted"])
        self.assertEqual(result["invalid_flags"]["reason"], "configuration_flags_invalid")
        self.assertFalse(result["invalid_mode"]["accepted"])
        self.assertEqual(result["invalid_mode"]["reason"], "apply_mode_invalid")
        self.assertEqual(result["logs"], 1)


if __name__ == "__main__":
    unittest.main()
