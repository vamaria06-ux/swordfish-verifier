import json
import os
import re
from typing import Dict, List, Any, Optional

class UniversalSchemaParser:
    
  def __init__(self, schemas_dir: str):
    self.schemas_dir = schemas_dir
    self.rules = {}
    self.all_definitions = {}
  
  def load_file(self, filepath: str) -> Dict:
    try:
      with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
    except Exception as e:
      print(f"Ошибка загрузки {filepath}: {e}")
      return {}
  
  