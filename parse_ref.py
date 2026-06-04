import os
import sys

# Ensure app package is in search path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.config_loader import import_old_config, save_config_json

def main():
    dat_path = "ref/Propylene.dat"
    print(f"Importing legacy DAT config: {dat_path}")
    
    config, warnings = import_old_config(dat_path)
    
    # Let's set a default output path relative to template
    if config.template_path:
        config.output_path = "ref/result.docx"
    
    print("\n--- DETECTED CONFIG ---")
    print(f"Template path: {config.template_path}")
    print(f"Output path: {config.output_path}")
    print(f"Number of Tags: {len(config.tags)}")
    print(f"Number of Tables: {len(config.tables)}")
    print(f"Number of Charts: {len(config.charts)}")
    print(f"Number of Topics: {len(config.topics)}")
    
    print("\n--- DETECTED TABLES (FIRST 5) ---")
    for i, t in enumerate(config.tables[:5]):
        print(f"Tag: {t.tag}\n  Excel: {t.excel_path}\n  Sheet: {t.sheet}\n  RangeA: {t.range_a}\n  RangeB: {t.range_b}\n  Use: {t.use}\n  Header: {t.header}")
        
    print("\n--- DETECTED CHARTS (FIRST 5) ---")
    for i, c in enumerate(config.charts[:5]):
        print(f"Tag: {c.tag}\n  Excel: {c.excel_path}\n  Sheet: {c.sheet}\n  Chart ID: {c.chart_id}")

    print(f"\nTotal warnings during parse: {len(warnings)}")
    if warnings:
        print("Warnings:")
        for w in warnings[:10]:
            print(f" - {w}")
        if len(warnings) > 10:
            print(f" ...and {len(warnings) - 10} more warnings.")

    # Save to json
    out_json = "configs/Propylene.json"
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    save_config_json(config, out_json)
    print(f"\nConfiguration saved to: {out_json}")

if __name__ == "__main__":
    main()
