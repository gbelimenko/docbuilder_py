import sys
import logging
import traceback

logger = logging.getLogger("DocBuilder.COM")

HAS_COM = False
win32 = None
pythoncom = None

if sys.platform == "win32":
    try:
        import win32com.client
        import pythoncom as pycom
        win32 = win32com.client
        pythoncom = pycom
        HAS_COM = True
        logger.info("pywin32 successfully initialized on Windows.")
    except Exception as e:
        logger.error(f"Failed to import pywin32 on Windows: {e}\n{traceback.format_exc()}")
else:
    logger.info("Running on non-Windows platform. COM automation will be mocked.")

class MockCOM:
    def __init__(self, name="COMObject"):
        self._name = name

    def __getattr__(self, attr):
        # Gracefully handle any property or method access
        if attr.startswith('_'):
            raise AttributeError(attr)
        logger.debug(f"Mock COM Access: {self._name}.{attr}")
        return MockCOM(f"{self._name}.{attr}")

    def __call__(self, *args, **kwargs):
        logger.debug(f"Mock COM Call: {self._name}({', '.join(map(str, args))})")
        return MockCOM(f"{self._name}_call_result")

    def __str__(self):
        return self._name

    def __repr__(self):
        return f"<MockCOM {self._name}>"

class MockRange(MockCOM):
    def CopyPicture(self, Appearance=1, Format=2):
        logger.info(f"Mock: Copied Excel Range {self._name} as picture (Appearance={Appearance}, Format={Format})")
        return True

class MockChart(MockCOM):
    def CopyPicture(self):
        logger.info(f"Mock: Copied Excel Chart {self._name} as picture")
        return True

class MockWorksheet(MockCOM):
    def Range(self, address):
        return MockRange(f"{self._name}.Range({address})")

    def ChartObjects(self, chart_id):
        return MockChart(f"{self._name}.ChartObjects({chart_id})")

class MockWorkbook(MockCOM):
    def Worksheets(self, sheet_name):
        return MockWorksheet(f"{self._name}.Worksheets({sheet_name})")
    
    def Close(self, SaveChanges=False):
        logger.info(f"Mock: Closed workbook {self._name} (SaveChanges={SaveChanges})")

class MockExcel(MockCOM):
    def __init__(self):
        super().__init__("Excel.Application")
        self.Visible = False
        self.DisplayAlerts = False
        self.Workbooks = MockWorkbooks()

    def Quit(self):
        logger.info("Mock: Excel Application Quit")

class MockWorkbooks(MockCOM):
    def Open(self, path):
        logger.info(f"Mock: Opened Excel workbook: {path}")
        return MockWorkbook(f"Workbook({path})")

class MockFind(MockCOM):
    def __init__(self, name):
        super().__init__(name)
        self.Text = ""

    def Execute(self, *args, **kwargs):
        logger.info(f"Mock Find: Executing text search for '{self.Text}'")
        # Return True for demonstration purposes to let mocks run through paste sequence
        return True

class MockSelection(MockCOM):
    def __init__(self):
        super().__init__("Word.Selection")
        self.Find = MockFind("Word.Selection.Find")

    def Delete(self):
        logger.info("Mock Selection: Deleted matching text tag")

    def Paste(self):
        logger.info("Mock Selection: Pasted image from clipboard")

class MockDocument(MockCOM):
    def SaveAs(self, path):
        logger.info(f"Mock Word: Saved document to {path}")

    def Close(self, SaveChanges=False):
        logger.info(f"Mock Word: Closed document (SaveChanges={SaveChanges})")

class MockWord(MockCOM):
    def __init__(self):
        super().__init__("Word.Application")
        self.Visible = False
        self.DisplayAlerts = False
        self.Documents = MockDocuments()
        self.Selection = MockSelection()

    def Quit(self):
        logger.info("Mock: Word Application Quit")

class MockDocuments(MockCOM):
    def Open(self, path):
        logger.info(f"Mock: Opened Word document: {path}")
        return MockDocument(f"Document({path})")

def get_excel_app():
    if HAS_COM:
        # Initialize COM in case of multithreading
        pythoncom.CoInitialize()
        return win32.DispatchEx("Excel.Application")
    else:
        return MockExcel()

def get_word_app():
    if HAS_COM:
        # Initialize COM in case of multithreading
        pythoncom.CoInitialize()
        return win32.DispatchEx("Word.Application")
    else:
        return MockWord()
