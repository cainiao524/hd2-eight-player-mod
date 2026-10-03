import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("scan_registration",ROOT/"scan_live_registration_state_20261003.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeReader:
    def __init__(self, pages):
        self.pages=pages
        self.used=0
    def read(self,address,size,executable=False):
        self.used += size
        return self.pages.get(address,b"\0"*size)

def query(address):
    return {"base":0x10000,"size":0x5000,"state":0x1000,"kind":0x20000,"protect":4}

def test_scan_reports_complete_limit():
    r=FakeReader({})
    stats,hits,errors=mod.scan_regions(r,query,{"x":b"ABC"},limit=0x2000,max_read=0x2000+16384)
    assert stats["termination_reason"] == "scan_limit_reached"
    assert stats["coverage_complete"] is True
    assert stats["truncated"] is False
    assert errors == []

def test_scan_reports_budget_incomplete():
    r=FakeReader({})
    stats,hits,errors=mod.scan_regions(r,query,{"x":b"ABC"},limit=0x3000,max_read=0x2000+16384)
    assert stats["termination_reason"] == "read_budget_exhausted"
    assert stats["coverage_complete"] is False
    assert stats["truncated"] is True
    assert errors and errors[0]["error"] == "read_budget_exhausted"

def test_scan_carries_pattern_across_pages():
    r=FakeReader({0x10000:b"X"*0xFFF+b"A",0x11000:b"BC"+b"\0"*(0x1000-2)})
    stats,hits,errors=mod.scan_regions(r,query,{"x":b"ABC"},limit=0x2000,max_read=0x2000+16384)
    assert hits == [{"pattern":"x","address":"0x10fff"}]
    assert errors == []

