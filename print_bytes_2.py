with open("ref/Propylene.dat", "rb") as f:
    data = f.read()

start = 2230
end = 2380
chunk = data[start:end]

print("Pos:   Hex:                                               ASCII:")
for idx in range(0, len(chunk), 16):
    pos = start + idx
    slice_bytes = chunk[idx:idx+16]
    hex_str = " ".join(f"{b:02x}" for b in slice_bytes)
    ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in slice_bytes)
    print(f"{pos:05d}: {hex_str:<47}  {ascii_str}")
