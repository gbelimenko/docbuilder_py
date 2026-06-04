with open("ref/Propylene.dat", "rb") as f:
    data = f.read()

header = b"\x00\x01\x00\x00\x00\xff\xff\xff\xff\x01\x00\x00\x00\x00\x00\x00\x00"
pos = 0
while True:
    idx = data.find(header, pos)
    if idx == -1:
        break
    print(f"Found header at position {idx}")
    pos = idx + len(header)
