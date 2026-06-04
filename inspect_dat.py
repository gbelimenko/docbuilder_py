import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from parse_nrbf import NRBFParser, resolve_refs

def custom_serializer(obj):
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, dict):
        return {k: custom_serializer(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [custom_serializer(x) for x in obj]
    return obj

def main():
    with open("ref/Propylene.dat", "rb") as f:
        data = f.read()
    
    parser = NRBFParser(data)
    objects = parser.parse()
    
    root = objects.get(1)
    resolved_root = resolve_refs(root, objects)
    
    # Save the full resolved structure to a JSON file
    with open("logs/resolved_propylene.json", "w", encoding="utf-8") as f:
        json.dump(custom_serializer(resolved_root), f, indent=2, ensure_ascii=False)
        
    print("Dumped resolved config structure to logs/resolved_propylene.json")
    print("Root class:", resolved_root.get("__class__"))
    print("Root keys:", list(resolved_root.keys()))

if __name__ == "__main__":
    main()
