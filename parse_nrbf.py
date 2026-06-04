import io
import struct

# Correct MS-NRBF Record Type Enums
SerializedStreamHeader = 0
ClassWithId = 1
SystemClassWithMembers = 2
ClassWithMembers = 3
SystemClassWithMembersAndTypes = 4
ClassWithMembersAndTypes = 5
BinaryObjectString = 6
BinaryArray = 7
MemberReference = 9
MessageEnd = 10
ObjectNull = 11
BinaryLibrary = 12
ObjectNullMultiple256 = 13
ObjectNullMultiple = 14
MemberPrimitiveTyped = 15
ArraySinglePrimitive = 16
ArraySingleObject = 17
ArraySingleString = 18

RECORD_NAMES = {
    0: "SerializedStreamHeader",
    1: "ClassWithId",
    2: "SystemClassWithMembers",
    3: "ClassWithMembers",
    4: "SystemClassWithMembersAndTypes",
    5: "ClassWithMembersAndTypes",
    6: "BinaryObjectString",
    7: "BinaryArray",
    9: "MemberReference",
    10: "MessageEnd",
    11: "ObjectNull",
    12: "BinaryLibrary",
    13: "ObjectNullMultiple256",
    14: "ObjectNullMultiple",
    15: "MemberPrimitiveTyped",
    16: "ArraySinglePrimitive",
    17: "ArraySingleObject",
    18: "ArraySingleString"
}

def read_7bit_encoded_int(f) -> int:
    val = 0
    shift = 0
    while True:
        b = f.read(1)
        if not b:
            raise EOFError("Unexpected EOF")
        byte = b[0]
        val |= (byte & 0x7f) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return val

def read_string(f) -> str:
    length = read_7bit_encoded_int(f)
    return f.read(length).decode("utf-8", errors="ignore")

class ClassInfo:
    def __init__(self, obj_id, name, member_count, member_names):
        self.obj_id = obj_id
        self.name = name
        self.member_count = member_count
        self.member_names = member_names
        self.binary_types = []
        self.additional_infos = []

class NRBFParser:
    def __init__(self, data: bytes):
        self.f = io.BytesIO(data)
        self.objects = {}       # Map of ObjectID -> deserialized value
        self.class_infos = {}   # Map of MetadataID -> ClassInfo
        self.library_names = {} # Map of LibID -> Name

    def parse(self):
        try:
            self._parse_records()
        except Exception as e:
            import traceback
            print(f"Parsing error: {e}")
            traceback.print_exc()
        return self.objects

    def _parse_records(self):
        while True:
            pos = self.f.tell()
            b = self.f.read(1)
            if not b:
                break
            rec_type = b[0]
            rec_name = RECORD_NAMES.get(rec_type, f"Unknown({rec_type})")
            print(f"Pos {pos:05d}: Record Type {rec_type} ({rec_name})")
            if rec_type == MessageEnd:
                continue
            self._parse_record(rec_type)

    def _parse_record(self, rec_type):
        if rec_type == SerializedStreamHeader:
            root_id, header_id, major, minor = struct.unpack("<iiii", self.f.read(16))
        elif rec_type == BinaryLibrary:
            lib_id = struct.unpack("<i", self.f.read(4))[0]
            lib_name = read_string(self.f)
            self.library_names[lib_id] = lib_name
        elif rec_type == BinaryObjectString:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            val = read_string(self.f)
            self.objects[obj_id] = val
        elif rec_type == ClassWithMembersAndTypes or rec_type == SystemClassWithMembersAndTypes:
            pos_id = self.f.tell()
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            pos_name = self.f.tell()
            name = read_string(self.f)
            pos_mc = self.f.tell()
            member_count = struct.unpack("<i", self.f.read(4))[0]
            print(f"  [DEBUG Class] pos_id={pos_id}, obj_id={obj_id}, pos_name={pos_name}, name='{name}', pos_mc={pos_mc}, member_count={member_count}")
            member_names = [read_string(self.f) for _ in range(member_count)]
            
            c_info = ClassInfo(obj_id, name, member_count, member_names)
            
            # Read types
            binary_types = [self.f.read(1)[0] for _ in range(member_count)]
            c_info.binary_types = binary_types
            
            # Additional type info
            additional_infos = []
            for bt in binary_types:
                if bt == 0: # Primitive
                    prim_type = self.f.read(1)[0]
                    additional_infos.append(prim_type)
                elif bt == 3 or bt == 4: # SystemClass or Class
                    cls_name = read_string(self.f)
                    lib_id = 0
                    if bt == 4:
                        lib_id = struct.unpack("<i", self.f.read(4))[0]
                    additional_infos.append((cls_name, lib_id))
                else:
                    additional_infos.append(None)
            c_info.additional_infos = additional_infos
            
            # Library ID
            if rec_type == ClassWithMembersAndTypes:
                lib_id = struct.unpack("<i", self.f.read(4))[0]
            
            print(f"  Class: {name}, member_names: {member_names}, binary_types: {binary_types}")
            self.class_infos[obj_id] = c_info
            
            # Read member values
            values = {}
            for name, bt, add_info in zip(member_names, binary_types, additional_infos):
                values[name] = self.read_value(bt, add_info)
            
            obj_data = {"__class__": name, **values}
            self.objects[obj_id] = obj_data

        elif rec_type == ClassWithId:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            metadata_id = struct.unpack("<i", self.f.read(4))[0]
            
            c_info = self.class_infos.get(metadata_id)
            if not c_info:
                raise ValueError(f"Class info metadata ID {metadata_id} not found")
                
            values = {}
            for name, bt, add_info in zip(c_info.member_names, c_info.binary_types, c_info.additional_infos):
                values[name] = self.read_value(bt, add_info)
                
            obj_data = {"__class__": c_info.name, **values}
            self.objects[obj_id] = obj_data

        elif rec_type == ArraySingleObject:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            length = struct.unpack("<i", self.f.read(4))[0]
            self.objects[obj_id] = self.read_array_elements(length, 2, None)

        elif rec_type == ArraySingleString:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            length = struct.unpack("<i", self.f.read(4))[0]
            self.objects[obj_id] = self.read_array_elements(length, 1, None)

        elif rec_type == ArraySinglePrimitive:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            length = struct.unpack("<i", self.f.read(4))[0]
            prim_type = self.f.read(1)[0]
            
            # size mapping:
            # Boolean=1 (1 byte), Byte=2 (1 byte), Char=3 (1 byte), Double=6 (8 bytes), Int32=8 (4 bytes), Int64=9 (8 bytes) etc.
            size_map = {1:1, 2:1, 3:1, 6:8, 8:4, 9:8, 11:4, 12:8, 13:8, 14:2, 15:4, 16:8}
            elem_size = size_map.get(prim_type, 1)
            arr = self.f.read(length * elem_size)
            self.objects[obj_id] = arr

        elif rec_type == BinaryArray:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            arr_type = self.f.read(1)[0]
            rank = struct.unpack("<i", self.f.read(4))[0]
            lengths = struct.unpack(f"<{rank}i", self.f.read(4 * rank))
            bt = self.f.read(1)[0]
            add_info = None
            if bt == 0:
                add_info = self.f.read(1)[0]
            elif bt == 3 or bt == 4:
                cls_name = read_string(self.f)
                lib_id = 0
                if bt == 4:
                    lib_id = struct.unpack("<i", self.f.read(4))[0]
                add_info = (cls_name, lib_id)
            
            total_elements = 1
            for l in lengths:
                total_elements *= l
                
            self.objects[obj_id] = self.read_array_elements(total_elements, bt, add_info)
            
        elif rec_type == ObjectNull:
            pass
        elif rec_type == ObjectNullMultiple256:
            self.f.read(1)
        elif rec_type == ObjectNullMultiple:
            self.f.read(4)
        else:
            raise ValueError(f"Unhandled record type {rec_type}")

    def read_array_elements(self, length, binary_type, additional_info):
        arr = []
        while len(arr) < length:
            pos = self.f.tell()
            b = self.f.read(1)
            if not b:
                break
            val_type = b[0]
            print(f"    read_array_elements: pos={pos:05d}, val_type={val_type}")
            if val_type == ObjectNull:
                arr.append(None)
            elif val_type == ObjectNullMultiple256:
                count = self.f.read(1)[0]
                print(f"      ObjectNullMultiple256: count={count}")
                arr.extend([None] * count)
            elif val_type == ObjectNullMultiple:
                count = struct.unpack("<i", self.f.read(4))[0]
                print(f"      ObjectNullMultiple: count={count}")
                arr.extend([None] * count)
            else:
                self.f.seek(-1, io.SEEK_CUR)
                val = self.read_value(binary_type, additional_info)
                print(f"      parsed value: {val}")
                arr.append(val)
        return arr

    def read_value(self, binary_type, additional_info):
        if binary_type == 0: # Primitive
            prim_type = additional_info
            if prim_type == 1: # Boolean
                return self.f.read(1)[0] != 0
            elif prim_type == 2: # Byte
                return self.f.read(1)[0]
            elif prim_type == 8: # Int32
                return struct.unpack("<i", self.f.read(4))[0]
            elif prim_type == 9: # Int64
                return struct.unpack("<q", self.f.read(8))[0]
            elif prim_type == 6: # Double
                return struct.unpack("<d", self.f.read(8))[0]
            elif prim_type == 11: # Single
                return struct.unpack("<f", self.f.read(4))[0]
            else:
                return self.f.read(1)[0]
        
        b = self.f.read(1)
        if not b:
            return None
        val_type = b[0]
        
        if val_type == MemberReference:
            ref_id = struct.unpack("<i", self.f.read(4))[0]
            return {"__ref__": ref_id}
        elif val_type == BinaryObjectString:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            val = read_string(self.f)
            self.objects[obj_id] = val
            return val
        elif val_type == ObjectNull:
            return None
        elif val_type == ObjectNullMultiple256:
            count = self.f.read(1)[0]
            return None
        elif val_type == ClassWithId:
            obj_id = struct.unpack("<i", self.f.read(4))[0]
            metadata_id = struct.unpack("<i", self.f.read(4))[0]
            c_info = self.class_infos[metadata_id]
            values = {}
            for name, bt, add_info in zip(c_info.member_names, c_info.binary_types, c_info.additional_infos):
                values[name] = self.read_value(bt, add_info)
            obj_data = {"__class__": c_info.name, **values}
            self.objects[obj_id] = obj_data
            return {"__ref__": obj_id}
        elif val_type in (ClassWithMembersAndTypes, SystemClassWithMembersAndTypes):
            self._parse_record(val_type)
            obj_id = max(self.objects.keys())
            return {"__ref__": obj_id}
        elif val_type in (ArraySingleObject, ArraySingleString, ArraySinglePrimitive, BinaryArray):
            self._parse_record(val_type)
            obj_id = max(self.objects.keys())
            return {"__ref__": obj_id}
        else:
            self.f.seek(-1, io.SEEK_CUR)
            return None

def resolve_refs(obj, objects):
    if isinstance(obj, dict):
        if "__ref__" in obj:
            ref_id = obj["__ref__"]
            ref_obj = objects.get(ref_id)
            if isinstance(ref_obj, dict) and "__ref__" in ref_obj:
                return ref_obj
            return resolve_refs(ref_obj, objects)
        else:
            return {k: resolve_refs(v, objects) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_refs(x, objects) for x in obj]
    return obj

def main():
    with open("ref/Propylene.dat", "rb") as f:
        data = f.read()
    
    parser = NRBFParser(data)
    objects = parser.parse()
    
    root = objects.get(1)
    resolved_root = resolve_refs(root, objects)
    
    print("\n--- RESOLVED OBJECT GRAPH ---")
    import pprint
    pprint.pprint(resolved_root, depth=4)

if __name__ == "__main__":
    main()
