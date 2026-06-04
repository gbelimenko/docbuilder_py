import re
import os
import zipfile
import logging
from typing import List, Set
from app.services.com_wrapper import get_word_app, HAS_COM

logger = logging.getLogger("DocBuilder.WordScanner")

# Regex to find tags: <TableTag_1>, <ChartTag_2>, <TOPIC...>
# Notice that inside XML, tags might be split by XML tags (e.g., <w:t><</w:t><w:t>TableTag_1></w:t>).
# To handle XML split tags, we will strip all XML tags from the XML content first!
RE_TAGS_COMBINED = re.compile(r"<(TableTag_\d+|ChartTag_\d+|TOPIC[^>]+)>", re.IGNORECASE)
RE_XML_TAGS = re.compile(r"<[^>]+>")

def scan_docx_zip(file_path: str) -> Set[str]:
    """
    Scans a docx/docm file by unzipping and extracting all matching tags from its XML components.
    This works cross-platform without requiring MS Word.
    """
    found_tags = set()
    if not zipfile.is_zipfile(file_path):
        raise ValueError("File is not a valid zipfile (.docx/.docm).")

    # Important files in a docx/docm zip where tags might reside
    xml_files = [
        "word/document.xml",
        "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
        "word/header1.xml", "word/header2.xml", "word/header3.xml",
        "word/footnotes.xml", "word/endnotes.xml"
    ]

    with zipfile.ZipFile(file_path, 'r') as zf:
        for xml_file in xml_files:
            if xml_file in zf.namelist():
                try:
                    content_bytes = zf.read(xml_file)
                    content_str = content_bytes.decode('utf-8', errors='ignore')
                    
                    # Strip XML tags to merge text splits (e.g. <w:t><</w:t><w:t>TableTag_1></w:t>)
                    clean_text = RE_XML_TAGS.sub("", content_str)
                    
                    # Find matches
                    for match in RE_TAGS_COMBINED.finditer(clean_text):
                        found_tags.add(f"<{match.group(1)}>")
                except Exception as e:
                    logger.debug(f"Failed to scan XML file {xml_file} inside zip: {e}")
                    
    return found_tags

def scan_word_com(file_path: str) -> Set[str]:
    """
    Scans a Word file using Microsoft Word COM interface (Windows only).
    Slow, but works for old binary .doc files.
    """
    found_tags = set()
    if not HAS_COM:
        raise RuntimeError("COM is not supported on this platform.")

    word = None
    doc = None
    try:
        word = get_word_app()
        word.Visible = False
        doc = word.Documents.Open(file_path)
        
        # Read full text content
        full_text = doc.Content.Text
        
        # Also scan headers/footers in all sections
        for section in doc.Sections:
            for header in section.Headers:
                if header.Exists:
                    full_text += "\n" + header.Range.Text
            for footer in section.Footers:
                if footer.Exists:
                    full_text += "\n" + footer.Range.Text

        for match in RE_TAGS_COMBINED.finditer(full_text):
            found_tags.add(f"<{match.group(1)}>")
            
    finally:
        if doc:
            try:
                doc.Close(False)
            except Exception:
                pass
        if word:
            try:
                word.Quit()
            except Exception:
                pass

    return found_tags

def scan_word_template(file_path: str) -> List[str]:
    """
    Scans the template Word file for tags using the most appropriate strategy.
    """
    if not os.path.exists(file_path):
        logger.error(f"Template file does not exist: {file_path}")
        return []

    logger.info(f"Scanning template for tags: {file_path}")
    tags = set()
    
    # Strategy 1: Cross-platform Zip parsing (Fast, works on Mac/Win)
    try:
        tags = scan_docx_zip(file_path)
        logger.info(f"Scanned via Zip extraction. Found {len(tags)} tags.")
    except Exception as e:
        logger.warning(f"Zip scan failed: {e}. Falling back to COM if on Windows.")
        
        # Strategy 2: COM Automation (Windows only)
        if HAS_COM:
            try:
                tags = scan_word_com(file_path)
                logger.info(f"Scanned via Word COM. Found {len(tags)} tags.")
            except Exception as com_err:
                logger.error(f"COM scan failed: {com_err}")
        else:
            logger.error("COM is not available. Cannot scan legacy binary .doc template.")

    sorted_tags = sorted(list(tags))
    return sorted_tags
