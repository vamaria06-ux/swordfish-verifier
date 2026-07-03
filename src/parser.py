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
  
  def get_resource_name(self, filename: str) -> str:
    match = re.match(r'([A-Za-z]+)\.v', filename)
    if match:
      return match.group(1)
    return filename.replace('.json', '')
  
  def extract_definition(self, schema: Dict, resource: str) -> Dict:
    definitions = schema.get('definitions', {})
    if resource in definitions:
      return definitions[resource]
    if len(definitions) == 1:
      return list(definitions.values())[0]
    return {}
  
  