import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services import config_loader, report_builder

def main():
    config_path = "configs/Propylene.json"
    print(f"Loading config: {config_path}")
    config = config_loader.load_config_json(config_path)
    
    print("\nStarting Report Build Simulation...")
    errors = report_builder.build_report(
        config=config,
        config_path=config_path,
        run_tables=True,
        run_charts=True,
        clean_tags=True,
        status_callback=lambda msg: print(f"  [STATUS] {msg}")
    )
    
    print("\nBuild completed.")
    if errors:
        print("Errors encountered:")
        for err in errors:
            print(f" - {err}")
    else:
        print("Success! No errors reported.")

if __name__ == "__main__":
    main()
