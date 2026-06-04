import os
import logging
import traceback
from typing import Callable, List, Dict
from app.models.config import ReportConfig
from app.services.com_wrapper import get_excel_app, get_word_app, HAS_COM
from app.utils.paths import resolve_dynamic_path

logger = logging.getLogger("DocBuilder.ReportBuilder")

def replace_tag_with_clipboard_image(
    word_app, 
    doc, 
    tag: str, 
    excel_width: float = None, 
    excel_height: float = None, 
    in_front: bool = False
) -> bool:
    """
    Finds the tag in the Word document, deletes it, and pastes the clipboard image.
    If in_front is True, converts it to a floating shape (In Front of Text)
    and resizes it to the exact Excel dimensions in points.
    """
    # Reset selection to the start of the document
    doc.Content.Select()
    
    find = word_app.Selection.Find
    find.ClearFormatting()
    find.Text = tag
    find.Replacement.Text = ""
    find.Forward = True
    find.Wrap = 1  # wdFindContinue
    find.Format = False
    find.MatchCase = True
    find.MatchWholeWord = False
    find.MatchWildcards = False
    
    replaced_count = 0
    # Search loop
    while find.Execute():
        word_app.Selection.Delete()
        word_app.Selection.Paste()
        replaced_count += 1
        
        # Position and size formatting for floating shapes (e.g. charts)
        if in_front and word_app.Selection.InlineShapes.Count > 0:
            inline_shape = word_app.Selection.InlineShapes(1)
            try:
                # Convert to floating shape (Shape object)
                shape = inline_shape.ConvertToShape()
                # wdWrapNone / wdWrapFront = 3 (In Front of Text)
                shape.WrapFormat.Type = 3 
                
                if excel_width and excel_height:
                    shape.Width = excel_width
                    shape.Height = excel_height
                    logger.info(f"Pasted chart: set size to {excel_width}x{excel_height} points, 'In Front of Text'.")
            except Exception as ex:
                logger.error(f"Failed to format floating shape for tag {tag}: {ex}")
        
    if replaced_count > 0:
        logger.info(f"Replaced tag '{tag}' {replaced_count} time(s).")
        return True
    else:
        logger.warning(f"Tag '{tag}' was not found in the document.")
        return False

def clean_remaining_tags(word_app, doc):
    """
    Cleans up any leftover tags matching patterns like <TableTag_X>, <ChartTag_Y>, <TOPIC...>
    by replacing them with empty strings.
    """
    doc.Content.Select()
    find = word_app.Selection.Find
    find.ClearFormatting()
    find.Replacement.ClearFormatting()
    find.Replacement.Text = ""
    find.Forward = True
    find.Wrap = 1  # wdFindContinue
    find.MatchWildcards = True
    
    patterns = [r"\<TableTag_[0-9]*\>", r"\<ChartTag_[0-9]*\>", r"\<TOPIC[!\>]*\>"]
    
    for pattern in patterns:
        find.Text = pattern
        find.Execute(Replace=2) # Replace All
        logger.info(f"Cleaned up remaining tags matching pattern: {pattern}")

def build_report(
    config: ReportConfig, 
    config_path: str = "",
    run_tables: bool = True, 
    run_charts: bool = True, 
    clean_tags: bool = False,
    status_callback: Callable[[str], None] = None
) -> List[str]:
    """
    Main report generation workflow.
    Directly opens the target Word file in-place, groups Excel operations,
    copies tables/charts, and pastes them with custom size/wrapping.
    """
    errors = []
    
    def log_status(msg: str):
        logger.info(msg)
        if status_callback:
            status_callback(msg)

    # 1. Resolve target output path (only one file path is used now, in-place edit)
    resolved_output = resolve_dynamic_path(config.output_path, config_path)
    
    if not resolved_output:
        config_dir = os.path.dirname(os.path.abspath(config_path)) if config_path else os.getcwd()
        resolved_output = os.path.normpath(os.path.join(config_dir, "result.docx"))

    log_status(f"Target Word file for compilation: {resolved_output}")

    if not resolved_output or not os.path.exists(resolved_output):
        err = f"Word file does not exist: {config.output_path} (resolved: {resolved_output})"
        log_status(f"ERROR: {err}")
        return [err]

    # 2. Group operations by Excel workbook path
    excel_groups: Dict[str, Dict[str, list]] = {}
    
    if run_tables:
        for tbl in config.tables:
            if not tbl.use:
                continue
            res_path = resolve_dynamic_path(tbl.excel_path, config_path)
            excel_groups.setdefault(res_path, {'tables': [], 'charts': []})['tables'].append(tbl)
            
    if run_charts:
        for chrt in config.charts:
            res_path = resolve_dynamic_path(chrt.excel_path, config_path)
            excel_groups.setdefault(res_path, {'tables': [], 'charts': []})['charts'].append(chrt)

    log_status(f"Grouped operations into {len(excel_groups)} unique Excel workbook(s).")

    # 3. Execution
    if not HAS_COM:
        log_status("Running on non-Windows platform. Simulating optimized COM operations...")
        for excel_path, items in excel_groups.items():
            log_status(f"Simulating: Opening workbook {excel_path} once...")
            for tbl in items['tables']:
                rng = f"{tbl.range_a}:{tbl.range_b}" if tbl.range_b else tbl.range_a
                log_status(f"  [Table] Copying range {rng} on sheet '{tbl.sheet}' for tag {tbl.tag}")
            for chrt in items['charts']:
                log_status(f"  [Chart] Copying chart ID {chrt.chart_id} on sheet '{chrt.sheet}' (size: simulated) for tag {chrt.tag}")
            log_status(f"Simulating: Closed workbook {excel_path}.")
            
        if clean_tags:
            log_status("Simulating: Cleaning up leftover tags in Word document...")
            
        log_status("Simulation complete.")
        return []

    # Windows COM Execution
    excel = None
    word = None
    doc = None
    
    try:
        log_status("Starting Microsoft Word...")
        word = get_word_app()
        word.Visible = False
        word.DisplayAlerts = False
        word.ScreenUpdating = False
        
        log_status("Starting Microsoft Excel...")
        excel = get_excel_app()
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.ScreenUpdating = False
        excel.Interactive = False

        log_status(f"Opening Word document in-place: {resolved_output}")
        doc = word.Documents.Open(resolved_output)

        # Process Excel workbooks
        for excel_path, items in excel_groups.items():
            if not os.path.exists(excel_path):
                err_msg = f"Excel file does not exist: {excel_path}"
                log_status(f"WARNING: {err_msg}")
                errors.append(err_msg)
                continue

            wb = None
            try:
                log_status(f"Opening workbook: {excel_path}")
                wb = excel.Workbooks.Open(excel_path, UpdateLinks=False, ReadOnly=True, IgnoreReadOnlyRecommended=True)
                
                # Copy & paste Tables (inline images, original layout flow)
                for tbl in items['tables']:
                    log_status(f"Processing Table tag {tbl.tag}...")
                    try:
                        ws = wb.Worksheets(tbl.sheet)
                        
                        if tbl.range_b:
                            rng_addr = f"{tbl.range_a}:{tbl.range_b}"
                            rng = ws.Range(rng_addr)
                        else:
                            start_cell = ws.Range(tbl.range_a)
                            rng = start_cell.CurrentRegion
                            log_status(f"Table range for {tbl.tag} is a single cell. Expanded to CurrentRegion: {rng.Address}")

                        rng.CopyPicture(Appearance=1, Format=2)
                        replace_tag_with_clipboard_image(word, doc, tbl.tag, in_front=False)
                    except Exception as ex:
                        tb = traceback.format_exc()
                        err = f"Failed to process Table tag {tbl.tag}: {ex}\n{tb}"
                        log_status(f"ERROR: {err}")
                        errors.append(f"Table tag {tbl.tag}: {ex}")
                        
                # Copy & paste Charts (floating shape, In Front of Text, exact size)
                for chrt in items['charts']:
                    log_status(f"Processing Chart tag {chrt.tag}...")
                    try:
                        ws = wb.Worksheets(chrt.sheet)
                        
                        # Activate sheet and temporarily make Excel visible for chart copying
                        ws.Activate()
                        excel.Visible = True
                        
                        chart_obj = ws.ChartObjects(chrt.chart_id)
                        chart_obj.Select()
                        
                        # Read dimensions in points
                        chart_width = float(chart_obj.Width)
                        chart_height = float(chart_obj.Height)
                        
                        chart_obj.CopyPicture(Appearance=1, Format=2)
                        replace_tag_with_clipboard_image(
                            word, doc, chrt.tag, 
                            excel_width=chart_width, 
                            excel_height=chart_height, 
                            in_front=True
                        )
                    except Exception as ex:
                        tb = traceback.format_exc()
                        err = f"Failed to process Chart tag {chrt.tag}: {ex}\n{tb}"
                        log_status(f"ERROR: {err}")
                        errors.append(f"Chart tag {chrt.tag}: {ex}")
                    finally:
                        try:
                            excel.Visible = False
                        except Exception:
                            pass
                        
            except Exception as ex:
                tb = traceback.format_exc()
                err = f"Failed to read Excel workbook {excel_path}: {ex}\n{tb}"
                log_status(f"ERROR: {err}")
                errors.append(f"Workbook {excel_path}: {ex}")
            finally:
                if wb:
                    try:
                        wb.Close(SaveChanges=False)
                    except Exception:
                        pass

        # Perform technical cleanup of leftover tags
        if clean_tags:
            log_status("Cleaning up remaining leftover tags in the Word document...")
            try:
                clean_remaining_tags(word, doc)
            except Exception as ex:
                err = f"Failed during technical cleanup: {ex}"
                log_status(f"ERROR: {err}")
                errors.append(err)

        # Save and close Word document
        log_status("Saving target Word document...")
        doc.Save()
        doc.Close(SaveChanges=False)
        doc = None
        log_status("Report built successfully.")
        
    except Exception as e:
        err = f"Fatal error during report generation: {e}"
        log_status(f"ERROR: {err}")
        errors.append(err)
        logger.error(traceback.format_exc())
        
    finally:
        # Restore settings and cleanup
        if doc:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        if word:
            try:
                word.ScreenUpdating = True
                word.Quit()
            except Exception:
                pass
        if excel:
            try:
                excel.ScreenUpdating = True
                excel.Interactive = True
                excel.Quit()
            except Exception:
                pass
                
    return errors
