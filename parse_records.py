import io
import struct

RECORD_TYPES = {
    0: "SerializedStreamHeader",
    1: "ClassWithId",
    2: "SystemClassWithMembers",
    3: "ClassWithMembers",
    4: "SystemClassWithMembersAndTypes",
    5: "ClassWithMembersAndTypes",
    6: "BinaryObjectString",
    9: "MemberReference",
    10: "MessageEnd",
    11: "ObjectNull",
    12: "MessageEndDeprecated",
    13: "MemberPrimitiveTyped",
    14: "ArraySinglePrimitive",
    15: "ArraySingleObject",
    16: "ArraySingleString",
    17: "BinaryArray"
}

def read_7bit_encoded_int(f) -> int:
    val = 0
    shift = 0
    while True:
        b = f.read(1)
        if not b:
            raise EOFError("Unexpected EOF reading 7bit int")
        byte = b[0]
        val |= (byte & 0x7f) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return val

def read_string(f) -> str:
    length = read_7bit_encoded_int(f)
    return f.read(length).decode("utf-8", errors="ignore")

def parse():
    with open("ref/Propylene.dat", "rb") as f:
        data = f.read()
    
    stream = io.BytesIO(data)
    
    while True:
        pos = stream.tell()
        b = stream.read(1)
        if not b:
            print("EOF reached.")
            break
        rec_type = b[0]
        rec_name = RECORD_TYPES.get(rec_type, f"Unknown({rec_type})")
        print(f"Pos {pos:05d}: Record Type {rec_type} ({rec_name})")
        
        if rec_type == 0: # SerializedStreamHeader
            root_id, header_id, major, minor = struct.unpack("<iiii", stream.read(16))
            print(f"  RootId: {root_id}, HeaderId: {header_id}, Version: {major}.{minor}")
        elif rec_type == 6: # BinaryObjectString
            obj_id = struct.unpack("<i", stream.read(4))[0]
            val = read_string(stream)
            print(f"  ObjectID: {obj_id}, String: {val}")
        elif rec_type == 9: # MemberReference
            ref_id = struct.unpack("<i", stream.read(4))[0]
            print(f"  RefID: {ref_id}")
        elif rec_type == 10: # MessageEnd
            break
        elif rec_type == 11: # ObjectNull
            pass
        elif rec_type == 14: # ArraySinglePrimitive
            # ObjectID, Length, PrimitiveType
            obj_id, length = struct.unpack("<ii", stream.read(8))
            prim_type = stream.read(1)[0]
            print(f"  ObjectID: {obj_id}, Length: {length}, PrimType: {prim_type}")
            stream.read(length) # skip values
        elif rec_type == 16: # ArraySingleString
            obj_id, length = struct.unpack("<ii", stream.read(8))
            print(f"  ObjectID: {obj_id}, Length: {length}")
        elif rec_type == 17: # BinaryArray
            obj_id = struct.unpack("<i", stream.read(4))[0]
            # binary array has complex structure, let's see how much we read
            # arrayType, rank, lengths, types...
            # Just skip or print
            print(f"  ObjectID: {obj_id}")
            break # break to check
        else:
            # We don't know the size, so let's break for now
            break

if __name__ == "__main__":
    parse()
