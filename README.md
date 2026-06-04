# DocBuilder Python MVP

Python-based desktop application replacement for the legacy `.NET` DocBuilder reporting tool. It automates report generation by scanning Word templates for tags (e.g. `<TableTag_1>`, `<ChartTag_2>`, `<TOPIC.Demand>`), copying pre-formatted tables and charts from Excel workbooks as pictures, and pasting them directly into Word at the tag locations.

## Features

1. **Modern Cross-Platform GUI**: Built with PySide6, featuring a premium dark-themed dashboard.
2. **Backward Compatibility**: Best-effort importer for legacy binary `.dat` files. Scans binary structures for ASCII/UTF-16 strings to extract tag mappings, Excel paths, sheets, and ranges/chart IDs.
3. **Template Tag Scanning**: Instantly reads a Word document (`.docx`/`.docm`) and detects all tags. Works 100x faster than COM by inspecting ZIP XML files directly, making tag scanning cross-platform.
4. **Excel Link Verification**: Validates whether the Excel files, sheet names, and range coordinates exist before generating reports.
5. **COM Automation / Mock Simulation**: 
   - **On Windows**: Uses Microsoft Office COM client (`pywin32`) to automate Excel and Word.
   - **On macOS/Linux**: Automatically falls back to simulation mode, allowing developers/users to test the UI, parse configs, scan Word files, and generate mockup reports without crashing.

---

## Project Structure

```
docbuilder_py/
  app/
    main.py                 # Application entry point
    gui/
      main_window.py        # MainWindow Layout and State manager
      tables_window.py      # Inline grid editor for Excel tables
      charts_window.py      # Inline grid editor for Excel charts
      tags_window.py        # List of tags and text editor for topic descriptions
      widgets/
        log_viewer.py       # Color-coded system log panel
    models/
      config.py             # Pydantic configuration schemas
    services/
      com_wrapper.py        # Win32 COM loader and macOS Mock simulator
      config_loader.py      # JSON config management
      dat_importer.py       # Heuristic binary DAT parser
      word_scanner.py       # Word template tag scanner
      report_builder.py     # Copy-paste automation engine
      excel_validator.py    # Link validation service
    utils/
      logging_config.py     # Logging setup with Qt signal routing
      paths.py              # Directory helper
  configs/                  # Active configurations storage
  logs/                     # Execution log files
  requirements.txt          # Python dependencies
  README.md                 # Project manual
```

---

## Installation & Setup

Ensure you have Python 3.11+ installed.

1. **Navigate to the repository folder**:
   ```bash
   cd /Users/getapple/Documents/python/docbuilder_py
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - **macOS/Linux**:
     ```bash
     source venv/bin/activate
     ```
   - **Windows**:
     ```cmd
     venv\Scripts\activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**:
   ```bash
   python app/main.py
   ```

---

## Usage Guide

### 1. Importing Legacy `.dat` Configs
- Click **Import old .DAT** in the sidebar.
- Choose your binary `.dat` file.
- The app will extract all tags and paths. Any unresolved sheets or ranges (which can happen due to binary formatter serialization obfuscation) will display warning logs.
- Review the tables and charts tabs to fix missing sheets/ranges.
- Click **Save JSON Config** to save the imported configuration. Next time, load the `.json` config file directly!

### 2. Scanning Word Templates
- Provide the path to your Word Template (or click **Browse**).
- Click **Scan Word Template**. The application will parse the document structure and append any new tags (like `<TOPIC...>`, tables, or charts) to the active tags list.

### 3. Validating Excel Links
- Select tables or charts. Click **Validate Row** to verify a single mapping.
- Or click **Validate Excel Links** in the sidebar to verify all connections in bulk.
- Output warnings will list files that are missing or sheets that cannot be found.

### 4. Building the Report
- Check that the **Word Template** and **Output File** paths are filled.
- Click **BUILD REPORT**.
- Excel and Word will run silently in the background, copying images, replacing tags, and generating the final report.
