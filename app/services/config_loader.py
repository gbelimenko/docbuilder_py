import json
import os
import logging
from typing import Tuple, List
from app.models.config import ReportConfig
from app.services.dat_importer import import_dat_file

logger = logging.getLogger("DocBuilder.ConfigLoader")

def load_config_json(file_path: str) -> ReportConfig:
    """
    Loads a ReportConfig from a JSON file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if hasattr(ReportConfig, "model_validate"):
        return ReportConfig.model_validate(data)
    else:
        return ReportConfig.parse_obj(data)

def save_config_json(config: ReportConfig, file_path: str) -> None:
    """
    Saves a ReportConfig to a JSON file.
    """
    if hasattr(config, "model_dump"):
        data = config.model_dump()
    else:
        data = config.dict()

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved configuration to: {file_path}")

def import_old_config(file_path: str) -> Tuple[ReportConfig, List[str]]:
    """
    Wrapper for importing legacy .dat configuration files.
    """
    return import_dat_file(file_path)
