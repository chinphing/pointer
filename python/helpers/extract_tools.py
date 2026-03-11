from math import e
import re, os, importlib, importlib.util, inspect
import json
import regex
from fnmatch import fnmatch
from types import ModuleType
from typing import Any, Type, TypeVar
from .dirty_json import DirtyJson
from .files import get_abs_path, deabsolute_path

try:
    import sloppy_xml as sloppyxml
    SLOPPYXML_AVAILABLE = True
except ImportError:
    SLOPPYXML_AVAILABLE = False


def xml_parse_dirty(xml_str: str) -> dict[str, Any] | None:
    if not xml_str or not isinstance(xml_str, str):
        return None

    try:
        return parse_xml_to_dict(xml_str.strip())
    except Exception:
        return None


def parse_xml_to_dict(xml_str: str) -> dict:
    """Parse XML format to dict using sloppy-xml for incomplete XML."""
    if not SLOPPYXML_AVAILABLE:
        raise ImportError("sloppy-xml not available")
    
    content = xml_str.strip()
    
    # Use sloppy-xml to parse incomplete XML
    try:
        parsed_tree = sloppyxml.tree_parse(content)
        # Convert ElementTree to dict
        result = element_to_dict(parsed_tree)
        return result
    except Exception as e:
        raise ValueError(f"Failed to parse XML with sloppy-xml: {e}")


def element_to_dict(element) -> dict:
    """Convert xml.etree.ElementTree.Element to dict."""
    result = {}
    
    for child in element.iter():
        tag = child.tag
        text = (child.text or "").strip()
        
        if tag == "tool_args":
            # Parse nested structure within tool_args
            result['tool_args'] = parse_xml_args_element(child)
        elif tag == "plans":
            # Parse plans as markdown list
            plans_text = text
            plans = []
            for line in plans_text.split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    plans.append(line[1:].strip())
                else:
                    plans.append(line.strip())
            if plans:
                result['plans'] = plans
        else:
            # Simple text content
            result[tag] = text
    
    return result


def parse_xml_args_element(element) -> dict:
    """Parse XML element's children as dict."""
    result = {}
    for child in element.iter():
        tag = child.tag
        text = (child.text or "").strip()
        
        # Try to convert to number
        try:
            if '.' in text:
                result[tag] = float(text)
            else:
                result[tag] = int(text)
        except ValueError:
            result[tag] = text
    
    return result


def convert_xml_to_dict(xml_str: str) -> dict:
    """Convert XML format to JSON for parsing - uses sloppy-xml."""
    return parse_xml_to_dict(xml_str)


# Keep legacy function names for compatibility
def extract_json_object_string(content):
    # Try XML format first (no outer <response> tag)
    xml_patterns = ['<thoughts>', '<tool_name>', '<headline>']
    if any(p in content for p in xml_patterns):
        try:
            json_str = json.dumps(convert_xml_to_dict(content))
            return json_str
        except Exception:
            pass  # Fall back to JSON parsing
    
    # Fall back to JSON format
    start = content.find('{')
    if start == -1:
        return ""

    # Find the first '{'
    end = content.rfind('}')
    if end == -1:
        return content[start:]
    else:
        return content[start:end+1]


def extract_json_string(content):
    # Regular expression pattern to match a JSON object
    pattern = r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]|"(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'

    # Search for the pattern in the content
    match = regex.search(pattern, content)

    if match:
        # Return the matched JSON string
        return match.group(0)
    else:
        return ""


def fix_json_string(json_string):
    # Function to replace unescaped line breaks within JSON string values
    def replace_unescaped_newlines(match):
        return match.group(0).replace('\n', '\\n')

    # Use regex to find string values and apply the replacement function
    fixed_string = re.sub(r'(?<=: ")(.*?)(?=")', replace_unescaped_newlines, json_string, flags=re.DOTALL)
    return fixed_string


T = TypeVar('T')  # Define a generic type variable

def import_module(file_path: str) -> ModuleType:
    # Handle file paths with periods in the name using importlib.util
    abs_path = get_abs_path(file_path)
    module_name = os.path.basename(abs_path).replace('.py', '')
    
    # Create the module spec and load the module
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {abs_path}")
        
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_classes_from_folder(folder: str, name_pattern: str, base_class: Type[T], one_per_file: bool = True) -> list[Type[T]]:
    classes = []
    abs_folder = get_abs_path(folder)

    # Get all .py files in the folder that match the pattern, sorted alphabetically
    py_files = sorted(
        [file_name for file_name in os.listdir(abs_folder) if fnmatch(file_name, name_pattern) and file_name.endswith(".py")]
    )

    # Iterate through the sorted list of files
    for file_name in py_files:
        file_path = os.path.join(abs_folder, file_name)
        # Use the new import_module function
        module = import_module(file_path)

        # Get all classes in the module
        class_list = inspect.getmembers(module, inspect.isclass)

        # Filter for classes that are subclasses of the given base_class
        # iterate backwards to skip imported superclasses
        for cls in reversed(class_list):
            if cls[1] is not base_class and issubclass(cls[1], base_class):
                classes.append(cls[1])
                if one_per_file:
                    break

    return classes

def load_classes_from_file(file: str, base_class: type[T], one_per_file: bool = True) -> list[type[T]]:
    classes = []
    # Use the new import_module function
    module = import_module(file)
    
    # Get all classes in the module
    class_list = inspect.getmembers(module, inspect.isclass)
    
    # Filter for classes that are subclasses of the given base_class
    # iterate backwards to skip imported superclasses
    for cls in reversed(class_list):
        if cls[1] is not base_class and issubclass(cls[1], base_class):
            classes.append(cls[1])
            if one_per_file:
                break
                
    return classes
