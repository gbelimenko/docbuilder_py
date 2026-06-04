import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.services.dat_importer import extract_strings_from_binary

def main():
    with open("ref/Propylene.dat", "rb") as f:
        binary_data = f.read()
        
    strings = extract_strings_from_binary(binary_data)
    
    os.makedirs("logs", exist_ok=True)
    out_path = "logs/dat_strings.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        for s in strings:
            f.write(s + "\n")
            
    print(f"Dumped {len(strings)} strings to {out_path}")

if __name__ == "__main__":
    main()
