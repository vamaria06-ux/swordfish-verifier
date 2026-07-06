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
  
  def extract_field_info(self, field_name: str, field_details: Dict, 
    definitions: Dict) -> Dict:
    info = {
        "name": field_name,
        "type": field_details.get('type', 'unknown'),
        "readonly": field_details.get('readonly', False),
        "description": field_details.get('description', ''),
        "versionAdded": field_details.get('versionAdded', '')
    }
        
    if 'enum' in field_details:
      info['enum'] = field_details['enum']
    if 'format' in field_details:
      info['format'] = field_details['format']
    if '$ref' in field_details:
      info['$ref'] = field_details['$ref']
      if '#/definitions/' in field_details['$ref']:
        ref_name = field_details['$ref'].replace('#/definitions/', '')
        if ref_name in definitions:
          ref_def = definitions[ref_name]
          if 'type' in ref_def:
            info['type'] = ref_def['type']
    if 'minimum' in field_details:
      info['minimum'] = field_details['minimum']
    if 'maximum' in field_details:
      info['maximum'] = field_details['maximum']
    if 'minLength' in field_details:
      info['minLength'] = field_details['minLength']
    if 'maxLength' in field_details:
      info['maxLength'] = field_details['maxLength']
    if 'pattern' in field_details:
      info['pattern'] = field_details['pattern']
    if 'units' in field_details:
      info['units'] = field_details['units']
    if field_details.get('type') == 'array' and 'items' in field_details:
      info['items'] = field_details['items']
      if '$ref' in field_details['items']:
        info['items_type'] = 'object'
      else:
        info['items_type'] = field_details['items'].get('type', 'unknown')
    
    return info
    
    def extract_enums(self, definitions: Dict) -> Dict[str, List[str]]:
      enums = {}
      for name, definition in definitions.items():
        if 'enum' in definition:
          enums[name] = definition['enum']
        if 'properties' in definition:
          for prop_name, prop_details in definition['properties'].items():
            if 'enum' in prop_details:
              enums[f"{name}.{prop_name}"] = prop_details['enum']
      return enums
    
    