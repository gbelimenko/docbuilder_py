from pydantic import BaseModel, Field
from typing import List, Optional

class TableItem(BaseModel):
    tag: str
    excel_path: str = ""
    sheet: str = ""
    range_a: str = ""
    range_b: str = ""
    use: bool = True
    header: bool = False

class ChartItem(BaseModel):
    tag: str
    excel_path: str = ""
    sheet: str = ""
    chart_id: int = 1

class TopicItem(BaseModel):
    tag: str
    text: Optional[str] = None

class ReportConfig(BaseModel):
    template_path: str = ""
    output_path: str = ""
    tags: List[str] = Field(default_factory=list)
    tables: List[TableItem] = Field(default_factory=list)
    charts: List[ChartItem] = Field(default_factory=list)
    topics: List[TopicItem] = Field(default_factory=list)
