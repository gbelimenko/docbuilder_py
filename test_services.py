import os
import sys
import logging

# Ensure app package is in search path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.utils.paths import ensure_dirs
from app.utils.logging_config import setup_logging
from app.services.config_loader import import_old_config

def create_mock_dat_file(filepath: str):
    """
    Creates a mock binary .dat file to test string parsing.
    Simulates a serialized stream containing tags, paths, sheets, and ranges.
    """
    # Create binary bytes mimicking .NET BinaryFormatter serialized data
    # with a mix of nulls, control chars, and printable UTF-8/UTF-16 strings
    data = bytearray()
    
    # Header block
    data.extend(b"\x00\x01\x00\x00\x00\xff\xff\xff\xff\x01\x00\x00\x00\x00\x00\x00\x00")
    
    # Word template path
    data.extend(b"\x0b\\temp_template.docx\x00")
    
    # TableTag_1 sequence
    data.extend(b"\x00\x00\x00\x12<TableTag_1>\x00\x00")
    # Excel path
    data.extend(b"\\\\ODIN\\departments\\Ethylene\\Ethylene TARs.xlsx\x00\x00")
    # Sheet name
    data.extend(b"\x06Europe\x00")
    # Range
    data.extend(b"\x07A1:H20\x00")
    
    # ChartTag_6 sequence
    data.extend(b"\x00\x00\x12<ChartTag_6>\x00\x00")
    # Excel path
    data.extend(b"\\\\ODIN\\departments\\Ethylene\\Ethylene fix.xlsx\x00\x00")
    # Sheet name
    data.extend(b"\x06Charts\x00")
    # Chart ID
    data.extend(b"\x017\x00") # ID 7
    
    # Topic sequence
    data.extend(b"\x00\x00<TOPIC.Demand.Propylene>\x00\x00")
    data.extend(b"This is the description paragraph of propylene demand in Europe.\x00")
    
    with open(filepath, "wb") as f:
        f.write(data)

def main():
    ensure_dirs()
    setup_logging()
    logger = logging.getLogger("DocBuilder.Test")
    
    mock_dat_path = "mock_project_config.dat"
    logger.info(f"Creating mock binary DAT file: {mock_dat_path}")
    create_mock_dat_file(mock_dat_path)
    
    logger.info("Running DAT importer on the mock file...")
    config, warnings = import_old_config(mock_dat_path)
    
    logger.info("DAT Import Results:")
    logger.info(f"Word Template Path: {config.template_path}")
    logger.info(f"Word Output Path: {config.output_path}")
    logger.info(f"Found Tags: {config.tags}")
    
    logger.info("Tables mapped:")
    for t in config.tables:
        logger.info(f"  Tag: {t.tag} | Excel: {t.excel_path} | Sheet: {t.sheet} | Range: {t.range_address}")
        
    logger.info("Charts mapped:")
    for c in config.charts:
        logger.info(f"  Tag: {c.tag} | Excel: {c.excel_path} | Sheet: {c.sheet} | ChartID: {c.chart_id}")
        
    logger.info("Topics mapped:")
    for tp in config.topics:
        logger.info(f"  Tag: {tp.tag} | Text Preview: {tp.text}")

    if warnings:
        logger.warning(f"Warnings reported during parsing: {warnings}")
        
    # Clean up mock file
    if os.path.exists(mock_dat_path):
        os.remove(mock_dat_path)
        logger.info(f"Cleaned up mock file: {mock_dat_path}")

if __name__ == "__main__":
    main()
