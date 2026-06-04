import os
import sys
import re
import zipfile
import shlex
import urllib.parse
import json
import xml.etree.ElementTree as ET

# Word processing namespaces
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def col_num_to_name(col_num):
    name = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        name = chr(65 + remainder) + name
    return name

def r1c1_to_a1(r1c1_str):
    pattern = r'^R(\d+)C(\d+)(?::R(\d+)C(\d+))?$'
    match = re.match(pattern, r1c1_str, re.IGNORECASE)
    if not match:
        return r1c1_str, ""
    r1, c1, r2, c2 = match.groups()
    a1_start = f"{col_num_to_name(int(c1))}{r1}"
    a1_end = f"{col_num_to_name(int(c2))}{r2}" if r2 and c2 else ""
    return a1_start, a1_end

def parse_ole_item(item_str):
    if '!' not in item_str:
        return None
    sheet_part, item_part = item_str.split('!', 1)
    sheet = sheet_part.strip("'\"")
    item_part = re.sub(r'\[[^\]]+\]', '', item_part).strip()
    
    # Try parsing range
    range_a, range_b = r1c1_to_a1(item_part)
    if range_a and not range_a.startswith('R'):
        return {
            "type": "table",
            "sheet": sheet,
            "range_a": range_a,
            "range_b": range_b
        }
    
    # If not R1C1 range, could be named range or chart
    chart_match = re.search(r'(?:chart\s*)?(\d+)', item_part, re.IGNORECASE)
    if chart_match:
        return {
            "type": "chart",
            "sheet": sheet,
            "chart_id": int(chart_match.group(1))
        }
    return {
        "type": "table",
        "sheet": sheet,
        "range_a": item_part,
        "range_b": ""
    }

def clean_excel_path(path_str):
    path_str = path_str.strip('"\'')
    if path_str.lower().startswith("file:///"):
        path_str = path_str[8:]
    path_str = urllib.parse.unquote(path_str)
    path_str = path_str.replace('/', '\\')
    
    # Check if it starts with a network share prefix
    is_network = False
    if path_str.startswith("\\\\"):
        is_network = True
        path_str = path_str.lstrip("\\")
        
    # Split by double backslashes and join with single backslash
    parts = [p for p in path_str.split("\\\\") if p]
    path_str = "\\".join(parts)
    
    if is_network:
        path_str = "\\\\" + path_str
        
    return path_str

def extract_chart_metadata(zf, chart_target):
    chart_part_name = f"word/{chart_target}"
    chart_rels_name = f"word/charts/_rels/{chart_target.split('/')[-1]}.rels"
    
    excel_path = ""
    # 1. Read relationships to find Excel file target
    if chart_rels_name in zf.namelist():
        c_rels_xml = zf.read(chart_rels_name).decode("utf-8", errors="ignore")
        root_rels = ET.fromstring(c_rels_xml)
        for r_node in root_rels:
            target = r_node.get("Target", "")
            if any(ext in target.lower() for ext in [".xlsx", ".xls", ".xlsm"]):
                excel_path = clean_excel_path(target)
                break
            
    # 2. Read chart XML to find sheet name from formulas
    sheet_name = "Sheet1"
    if chart_part_name in zf.namelist():
        c_content = zf.read(chart_part_name).decode("utf-8", errors="ignore")
        formulas = re.findall(r'<c:f>([^<]+)</c:f>', c_content)
        for f in formulas:
            if '!' in f:
                sheet_name = f.split('!')[0].replace('$', '').strip("'")
                break
                
    return excel_path, sheet_name

def scan_containers(xml_root):
    # Find all containers (body, tc, hdr, ftr) in the XML root
    containers = []
    if xml_root.tag in [f"{{{W_NS}}}hdr", f"{{{W_NS}}}ftr"]:
        containers.append(xml_root)
    for elem in xml_root.iter():
        if elem.tag in [f"{{{W_NS}}}body", f"{{{W_NS}}}tc"]:
            containers.append(elem)
    return containers

def main():
    src_docm = "ref/BUTADIENE_23_5_June_2026.docm"
    if len(sys.argv) > 1:
        src_docm = sys.argv[1]
        
    if not os.path.exists(src_docm):
        print(f"Error: Source file does not exist: {src_docm}")
        sys.exit(1)
        
    base_name = os.path.splitext(os.path.basename(src_docm))[0]
    dir_name = os.path.dirname(src_docm)
    
    # We resolve paths to absolute to store in JSON
    abs_src_docm = os.path.abspath(src_docm)
    abs_dest_docm = os.path.abspath(os.path.join(dir_name, f"{base_name}_tags.docm"))
    dest_json = os.path.join(dir_name, f"{base_name}.json")
    
    print(f"Reading layout template: {src_docm}")
    
    # Register namespaces to preserve prefixes in Output
    ET.register_namespace('w', W_NS)
    ET.register_namespace('wp', WP_NS)
    ET.register_namespace('c', C_NS)
    ET.register_namespace('r', R_NS)
    
    # 1. Read document relationships
    doc_rels = {}
    with zipfile.ZipFile(src_docm, 'r') as zf:
        if "word/_rels/document.xml.rels" in zf.namelist():
            rels_content = zf.read("word/_rels/document.xml.rels")
            root_rels = ET.fromstring(rels_content)
            for r_node in root_rels:
                rid = r_node.get("Id")
                target = r_node.get("Target")
                doc_rels[rid] = target
                
    # 2. Parse and open the zip to read XML roots
    xml_roots = {}
    xml_targets = []
    
    with zipfile.ZipFile(src_docm, 'r') as zf:
        # Find XML targets
        xml_targets.append("word/document.xml")
        for name in zf.namelist():
            if (name.startswith("word/header") or name.startswith("word/footer")) and name.endswith(".xml"):
                xml_targets.append(name)
                
        # Parse XML roots
        for name in xml_targets:
            if name in zf.namelist():
                content = zf.read(name)
                # Register namespaces dynamically from the XML declarations
                xmlns_pattern = re.compile(r'xmlns:([^=]+)="([^"]+)"')
                for prefix, uri in xmlns_pattern.findall(content.decode("utf-8", errors="ignore")):
                    ET.register_namespace(prefix, uri)
                xml_roots[name] = ET.fromstring(content)

    tables_info = []
    charts_info = []
    
    # 3. First Pass: Find all drawings containing charts and collect their metadata
    # We scan only paragraphs that are DIRECT children of containers to avoid double-processing.
    with zipfile.ZipFile(src_docm, 'r') as zf:
        for name, root in xml_roots.items():
            containers = scan_containers(root)
            for container in containers:
                for child in container:
                    if child.tag == f"{{{W_NS}}}p":
                        for run in child:
                            if run.tag == f"{{{W_NS}}}r":
                                chart_ref = run.find(f".//{{{C_NS}}}chart")
                                if chart_ref is not None:
                                    rid = chart_ref.get(f"{{{R_NS}}}id")
                                    chart_target = doc_rels.get(rid)
                                    if chart_target:
                                        excel_path, sheet_name = extract_chart_metadata(zf, chart_target)
                                        charts_info.append({
                                            "rid": rid,
                                            "run": run,
                                            "excel_path": excel_path,
                                            "sheet": sheet_name,
                                            "xml_name": name
                                        })

    # Group charts by (excel_path, sheet) case-insensitively
    chart_groups = {}
    for c in charts_info:
        # Group by lowercase path and sheet to handle casing discrepancies like ODIN vs Odin
        key = (c["excel_path"].lower(), c["sheet"].lower())
        chart_groups.setdefault(key, []).append(c)
        
    final_charts = []
    chart_counter = 1
    
    # Assign chart_id sequentially within each sheet, and replace run text in the tree
    for key, c_list in chart_groups.items():
        # Assign IDs in the order they appear in the document
        for sheet_idx, c in enumerate(c_list):
            tag_text = f"<ChartTag_{chart_counter}>"
            excel_chart_id = sheet_idx + 1 # 1-based sequential index
            
            final_charts.append({
                "tag": tag_text,
                "excel_path": c["excel_path"],
                "sheet": c["sheet"],
                "chart_id": excel_chart_id
            })
            
            # Replace run element text in-place in the tree
            run = c["run"]
            run.clear()
            t_elem = ET.SubElement(run, f"{{{W_NS}}}t")
            t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            t_elem.text = tag_text
            
            print(f"Chart replaced: {tag_text} -> Excel '{c['excel_path']}', Sheet '{c['sheet']}', ID {excel_chart_id}")
            chart_counter += 1

    # 4. Second Pass: Process OLE fields (tables) container by container
    for name, root in xml_roots.items():
        containers = scan_containers(root)
        for container in containers:
            # Build sequence of runs/blocks
            children = list(container)
            seq = []
            for child_idx, child in enumerate(children):
                if child.tag == f"{{{W_NS}}}p":
                    for r_idx, run in enumerate(child):
                        if run.tag == f"{{{W_NS}}}r":
                            seq.append({
                                "type": "run",
                                "element": run,
                                "parent_p": child,
                                "child_idx": child_idx,
                                "run_idx": r_idx
                            })
                else:
                    seq.append({
                        "type": "block",
                        "element": child,
                        "child_idx": child_idx
                    })
                    
            # Identify fields
            fields = []
            active_field = None
            for idx, token in enumerate(seq):
                if token["type"] == "run":
                    run = token["element"]
                    fld_char = run.find(f"{{{W_NS}}}fldChar")
                    if fld_char is not None:
                        fld_type = fld_char.get(f"{{{W_NS}}}fldCharType")
                        if fld_type == "begin":
                            active_field = {
                                "start_idx": idx,
                                "instr_parts": [],
                                "tokens": [token]
                            }
                        elif fld_type == "end" and active_field is not None:
                            active_field["end_idx"] = idx
                            active_field["tokens"].append(token)
                            fields.append(active_field)
                            active_field = None
                            
                    if active_field is not None and token not in active_field["tokens"]:
                        active_field["tokens"].append(token)
                        instr_texts = run.findall(f"{{{W_NS}}}instrText")
                        for it in instr_texts:
                            if it.text:
                                active_field["instr_parts"].append(it.text)
                elif token["type"] == "block":
                    if active_field is not None:
                        active_field["tokens"].append(token)
                        
            # Filter OLE LINK fields
            ole_fields = []
            for f in fields:
                instr_str = "".join(f["instr_parts"]).strip()
                if instr_str.upper().startswith("LINK"):
                    ole_fields.append(f)
                    
            # Replace OLE fields in reverse order of start_idx
            for f in sorted(ole_fields, key=lambda x: x["start_idx"], reverse=True):
                instr_str = "".join(f["instr_parts"]).strip()
                try:
                    args = shlex.split(instr_str, posix=False)
                except Exception:
                    continue
                if len(args) < 4:
                    continue
                    
                excel_path = clean_excel_path(args[2])
                item_str = args[3].strip('"\'')
                
                ole_info = parse_ole_item(item_str)
                if not ole_info:
                    continue
                    
                table_idx = len(tables_info) + 1
                tag_text = f"<TableTag_{table_idx}>"
                
                tables_info.append({
                    "tag": tag_text,
                    "excel_path": excel_path,
                    "sheet": ole_info.get("sheet", ""),
                    "range_a": ole_info.get("range_a", ""),
                    "range_b": ole_info.get("range_b", ""),
                    "use": True,
                    "header": False
                })
                
                # Perform replacement in container
                tokens = f["tokens"]
                token_start = tokens[0]
                token_end = tokens[-1]
                p_start = token_start["parent_p"]
                p_end = token_end["parent_p"]
                c_start = token_start["child_idx"]
                c_end = token_end["child_idx"]
                
                # Create replacement run
                new_run = ET.Element(f"{{{W_NS}}}r")
                t_elem = ET.SubElement(new_run, f"{{{W_NS}}}t")
                t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                t_elem.text = tag_text
                
                if c_start == c_end:
                    # Same paragraph field
                    runs = list(p_start)
                    p_start.clear()
                    for r_idx, run in enumerate(runs):
                        if r_idx < token_start["run_idx"]:
                            p_start.append(run)
                        elif r_idx == token_start["run_idx"]:
                            p_start.append(new_run)
                        elif r_idx > token_end["run_idx"]:
                            p_start.append(run)
                else:
                    # Multi-paragraph/block field
                    # 1. Modify p_start
                    runs_start = list(p_start)
                    p_start.clear()
                    for r_idx, run in enumerate(runs_start):
                        if r_idx < token_start["run_idx"]:
                            p_start.append(run)
                    p_start.append(new_run)
                    
                    # 2. Modify p_end
                    runs_end = list(p_end)
                    p_end.clear()
                    for r_idx, run in enumerate(runs_end):
                        if r_idx > token_end["run_idx"]:
                            p_end.append(run)
                            
                    # 3. Remove intermediate sibling blocks
                    siblings = list(container)
                    for k in range(c_start + 1, c_end):
                        try:
                            container.remove(siblings[k])
                        except ValueError:
                            pass
                            
                    # 4. Clean up p_end if empty
                    if len(p_end) == 0:
                        try:
                            container.remove(p_end)
                        except ValueError:
                            pass
                print(f"Table OLE field replaced: {tag_text} -> Excel '{excel_path}', Sheet '{ole_info.get('sheet')}', Range {ole_info.get('range_a')}:{ole_info.get('range_b')}")

    # Reverse tables list to match sequential order in document (since we processed from bottom to top)
    tables_info.reverse()
    for idx, t in enumerate(tables_info):
        old_tag = t["tag"]
        new_tag = f"<TableTag_{idx+1}>"
        t["tag"] = new_tag
        # Update in the XML trees
        for name, root in xml_roots.items():
            for node in root.iter(f"{{{W_NS}}}t"):
                if node.text == old_tag:
                    node.text = new_tag

    # 5. Save the modified Word document package
    print(f"Saving new layout: {abs_dest_docm}")
    temp_zip_data = {}
    
    # Serialize updated XML roots
    for name, root in xml_roots.items():
        temp_zip_data[name] = ET.tostring(root, encoding="utf-8")
        
    # Copy all other files directly from original zip
    with zipfile.ZipFile(src_docm, 'r') as zf:
        for name in zf.namelist():
            if name not in temp_zip_data:
                temp_zip_data[name] = zf.read(name)
                
    # Write to new zip
    with zipfile.ZipFile(abs_dest_docm, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in temp_zip_data.items():
            zf.writestr(name, data)
            
    # 6. Generate JSON config file
    config_data = {
        "template_path": abs_dest_docm,
        "output_path": abs_dest_docm,
        "tags": [t["tag"] for t in tables_info] + [c["tag"] for c in final_charts],
        "tables": tables_info,
        "charts": final_charts,
        "topics": []
    }
    
    with open(dest_json, 'w', encoding='utf-8') as jf:
        json.dump(config_data, jf, ensure_ascii=False, indent=2)
        
    print(f"JSON configuration generated: {dest_json}")
    print(f"Process completed successfully. Generated {len(tables_info)} table tags and {len(final_charts)} chart tags.")

if __name__ == "__main__":
    main()
