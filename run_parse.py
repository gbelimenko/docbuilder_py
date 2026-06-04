import io
import struct
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from parse_nrbf import NRBFParser, resolve_refs

class VerboseParser(NRBFParser):
    def _parse_record(self, rec_type):
        pos = self.f.tell() - 1
        print(f"[{pos:05d}] parsing record {rec_type}")
        super()._parse_record(rec_type)

    def read_value(self, binary_type, additional_info):
        pos = self.f.tell()
        val = super().read_value(binary_type, additional_info)
        print(f"  [{pos:05d}] read_value(bt={binary_type}, info={additional_info}) -> {val}")
        return val

def main():
    with open("ref/Propylene.dat", "rb") as f:
        data = f.read()
    
    parser = VerboseParser(data)
    objects = parser.parse()
    
    root = objects.get(1)
    resolved_root = resolve_refs(root, objects)
    
    import pprint
    print("\n--- RESOLVED OBJECT GRAPH ---")
    pprint.pprint(resolved_root)
    print("\nSUCCESS!")

if __name__ == "__main__":
    main()
