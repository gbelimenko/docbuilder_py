import zipfile
import re

docm_path = "ref/BUTADIENE_23_5_June_2026.docm"

print("Reading zip files...")
with zipfile.ZipFile(docm_path, 'r') as z:
    for name in z.namelist():
        if "document.xml" in name or "rels" in name:
            print(f"  - {name} (size: {z.getinfo(name).file_size})")

print("\nSearching for LINK in word/document.xml...")
with zipfile.ZipFile(docm_path, 'r') as z:
    doc_xml = z.read("word/document.xml").decode("utf-8", errors="ignore")

# Find occurrences of LINK in document.xml
links = re.findall(r'LINK[^\"]*\"[^\"]*\"[^\"]*\"[^\"]*\"', doc_xml)
print(f"Found {len(links)} direct regex LINK matches.")
for i, l in enumerate(links[:5]):
    print(f"  {i+1}: {l[:150]}")

# Find any <w:instrText> tags
instrs = re.findall(r'<w:instrText[^>]*>([^<]+)</w:instrText>', doc_xml)
link_instrs = [ins for ins in instrs if "LINK" in ins]
print(f"\nFound {len(link_instrs)} <w:instrText> nodes containing 'LINK'.")
for i, ins in enumerate(link_instrs[:10]):
    print(f"  {i+1}: {ins.strip()}")

# Find <o:OLEObject> tags
ole_objects = re.findall(r'<o:OLEObject[^>]*>', doc_xml)
print(f"\nFound {len(ole_objects)} <o:OLEObject> tags.")
for i, ole in enumerate(ole_objects[:10]):
    print(f"  {i+1}: {ole[:150]}")
