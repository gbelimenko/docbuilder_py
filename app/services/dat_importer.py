import os
import logging
from typing import Tuple, List
from app.models.config import ReportConfig, TableItem, ChartItem, TopicItem
from app.utils.nrbf_parser import NRBFParser, resolve_refs

logger = logging.getLogger("DocBuilder.DatImporter")

def import_dat_file(file_path: str) -> Tuple[ReportConfig, List[str]]:
    """
    Parses a legacy binary .dat file using MS-NRBF binary deserialization,
    extracts the structured tags, tables, and charts, and returns a ReportConfig.
    All paths remain original, matching what was saved on the work PC.
    """
    warnings = []
    if not os.path.exists(file_path):
        warnings.append(f"File not found: {file_path}")
        return ReportConfig(), warnings

    try:
        with open(file_path, "rb") as f:
            binary_data = f.read()
    except Exception as e:
        warnings.append(f"Failed to read binary file: {e}")
        return ReportConfig(), warnings

    try:
        parser = NRBFParser(binary_data)
        objects = parser.parse()
        
        # The root object is typically ID 1
        root = objects.get(1)
        if not root:
            # Fallback: search for the first dict that looks like the root config
            for obj in objects.values():
                if isinstance(obj, dict) and "<Tags>k__BackingField" in obj:
                    root = obj
                    break

        if not root:
            raise ValueError("Could not find root configuration object in serialized stream.")
            
        resolved_root = resolve_refs(root, objects)
    except Exception as e:
        logger.error(f"NRBF parsing failed: {e}", exc_info=True)
        warnings.append(f"NRBF Parser Error: {e}")
        return ReportConfig(), warnings

    # 1. Word template path
    template_path = resolved_root.get("<SamplePath>k__BackingField", "")
    if not template_path:
        # Fallback to older field names if any
        template_path = resolved_root.get("SamplePath", "")
    
    # Clean up string if it's not a string
    if not isinstance(template_path, str):
        template_path = ""
        
    logger.info(f"Parsed template path: {template_path}")

    # 2. Parse Tags list to identify all tags and topics
    all_tags = []
    topics = []
    
    tags_field = resolved_root.get("<Tags>k__BackingField") or {}
    tags_items = tags_field.get("_items", []) if isinstance(tags_field, dict) else []
    
    for item in tags_items:
        if not isinstance(item, dict):
            continue
        
        tag_name = item.get("<Name>k__BackingField") or item.get("Name")
        if not tag_name or not isinstance(tag_name, str):
            continue
            
        all_tags.append(tag_name)
        
        # TagType: 0 = Topic, 1 = Chart, 2 = Table
        type_obj = item.get("<Type>k__BackingField") or item.get("Type") or {}
        tag_type = 0
        if isinstance(type_obj, dict):
            tag_type = type_obj.get("value__", 0)
        elif isinstance(type_obj, int):
            tag_type = type_obj
            
        if tag_type == 0:
            # It's a topic tag
            topics.append(TopicItem(tag=tag_name, text=None))

    # 3. Parse Tables list
    tables = []
    tables_field = resolved_root.get("<Tables>k__BackingField") or {}
    tables_items = tables_field.get("_items", []) if isinstance(tables_field, dict) else []
    
    for item in tables_items:
        if not isinstance(item, dict):
            continue
            
        tag = item.get("<Tag>k__BackingField") or item.get("Tag", "")
        link = item.get("<Link>k__BackingField") or item.get("Link", "")
        sheet = item.get("<SheetId>k__BackingField") or item.get("SheetId", "")
        range_a = item.get("<RangeA>k__BackingField") or item.get("RangeA", "")
        range_b = item.get("<RangeB>k__BackingField") or item.get("RangeB", "")
        use = item.get("<Use>k__BackingField")
        header = item.get("<Header>k__BackingField")
        
        if use is None:
            use = item.get("Use", True)
        if header is None:
            header = item.get("Header", False)
            
        tables.append(TableItem(
            tag=tag,
            excel_path=link,
            sheet=sheet,
            range_a=range_a,
            range_b=range_b,
            use=bool(use),
            header=bool(header)
        ))

    # 4. Parse Charts list
    charts = []
    charts_field = resolved_root.get("<Charts>k__BackingField") or {}
    charts_items = charts_field.get("_items", []) if isinstance(charts_field, dict) else []
    
    for item in charts_items:
        if not isinstance(item, dict):
            continue
            
        tag = item.get("<Tag>k__BackingField") or item.get("Tag", "")
        link = item.get("<Link>k__BackingField") or item.get("Link", "")
        sheet = item.get("<SheetId>k__BackingField") or item.get("SheetId", "")
        chart_id_val = item.get("<ChartId>k__BackingField") or item.get("ChartId", 1)
        
        try:
            chart_id = int(chart_id_val)
        except (ValueError, TypeError):
            chart_id = 1
            
        charts.append(ChartItem(
            tag=tag,
            excel_path=link,
            sheet=sheet,
            chart_id=chart_id
        ))

    config = ReportConfig(
        template_path=template_path,
        output_path="", # Output path is set by the user or left blank for now
        tags=all_tags,
        tables=tables,
        charts=charts,
        topics=topics
    )
    
    logger.info(f"DAT import parsed: {len(config.tables)} tables, {len(config.charts)} charts, {len(config.topics)} topics.")
    return config, warnings
