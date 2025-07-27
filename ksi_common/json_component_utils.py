"""Utilities for creating components with nested JSON content safely."""

import base64
import json
import re
from typing import Dict, Any, Optional, List, Tuple


def encode_json_content(content: str, method: str = "base64") -> Tuple[str, Dict[str, Any]]:
    """
    Encode content containing nested JSON to avoid parsing issues.
    
    Args:
        content: The component content that may contain nested JSON
        method: Encoding method - "base64" or "placeholder"
        
    Returns:
        Tuple of (encoded_content, metadata)
    """
    if method == "base64":
        # Simple base64 encoding of entire content
        encoded = base64.b64encode(content.encode()).decode()
        return f"BASE64:{encoded}", {"encoding": "base64"}
    
    elif method == "placeholder":
        # Find and replace JSON blocks with placeholders
        json_pattern = r'\{["\']event["\']\s*:\s*["\'][^"\']+["\']\s*,\s*["\']data["\']\s*:\s*\{[^}]+\}\s*\}'
        matches = list(re.finditer(json_pattern, content))
        
        if not matches:
            return content, {}
        
        modified_content = content
        replacements = {}
        
        for i, match in enumerate(matches):
            json_str = match.group(0)
            placeholder = f"{{{{JSON_BLOCK_{i}}}}}"
            replacements[f"JSON_BLOCK_{i}"] = json_str
            modified_content = modified_content.replace(json_str, placeholder)
        
        return modified_content, {"json_replacements": replacements}
    
    else:
        raise ValueError(f"Unknown encoding method: {method}")


def decode_json_content(content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Decode content that was encoded to handle nested JSON.
    
    Args:
        content: The encoded content
        metadata: Metadata containing decoding information
        
    Returns:
        The decoded original content
    """
    # Handle base64 encoding
    if content.startswith("BASE64:"):
        try:
            return base64.b64decode(content[7:]).decode()
        except Exception:
            return content  # Return as-is if decoding fails
    
    # Handle placeholder replacements
    if metadata and "json_replacements" in metadata:
        decoded_content = content
        for placeholder, json_str in metadata["json_replacements"].items():
            # Handle both {{PLACEHOLDER}} and PLACEHOLDER formats
            decoded_content = decoded_content.replace(f"{{{{{placeholder}}}}}", json_str)
            decoded_content = decoded_content.replace(placeholder, json_str)
        return decoded_content
    
    return content


def prepare_component_with_json(
    name: str,
    content: str,
    component_type: str = "component",
    encoding_method: str = "base64",
    **kwargs
) -> Dict[str, Any]:
    """
    Prepare a component creation request with safe JSON handling.
    
    Args:
        name: Component name
        content: Component content (may contain nested JSON)
        component_type: Type of component
        encoding_method: How to encode nested JSON
        **kwargs: Additional parameters for the creation request
        
    Returns:
        Dictionary ready to be sent to composition:create_component
    """
    # Encode the content
    encoded_content, encoding_metadata = encode_json_content(content, encoding_method)
    
    # Build the request
    request_data = {
        "name": name,
        "content": encoded_content,
        "type": component_type
    }
    
    # Add metadata if using placeholder method
    if encoding_metadata:
        if "metadata" not in kwargs:
            kwargs["metadata"] = {}
        kwargs["metadata"].update(encoding_metadata)
    
    # Add any additional parameters
    request_data.update(kwargs)
    
    return request_data


def extract_json_examples_from_content(content: str) -> List[Dict[str, Any]]:
    """
    Extract JSON examples from component content.
    
    Args:
        content: Component content that may contain JSON examples
        
    Returns:
        List of parsed JSON objects found in the content
    """
    json_pattern = r'\{["\']event["\']\s*:\s*["\'][^"\']+["\']\s*,\s*["\']data["\']\s*:\s*\{[^}]+\}\s*\}'
    matches = re.findall(json_pattern, content)
    
    json_examples = []
    for match in matches:
        try:
            # Clean up the JSON string and parse it
            json_obj = json.loads(match)
            json_examples.append(json_obj)
        except json.JSONDecodeError:
            # If direct parsing fails, try to clean it up
            cleaned = match.replace("'", '"')
            try:
                json_obj = json.loads(cleaned)
                json_examples.append(json_obj)
            except:
                pass  # Skip malformed JSON
    
    return json_examples


def create_json_aware_component_content(
    base_content: str,
    json_instructions: List[Dict[str, Any]],
    instruction_format: str = "placeholder"
) -> str:
    """
    Create component content with JSON instructions in a safe format.
    
    Args:
        base_content: The base component content without JSON
        json_instructions: List of JSON objects to include as instructions
        instruction_format: How to format the instructions - "placeholder" or "yaml"
        
    Returns:
        Component content with JSON instructions safely embedded
    """
    if instruction_format == "placeholder":
        # Add placeholders that will be replaced at runtime
        content = base_content
        for i, instruction in enumerate(json_instructions):
            placeholder = f"{{{{JSON_INSTRUCTION_{i}}}}}"
            content = content.replace(f"[JSON_INSTRUCTION_{i}]", placeholder)
        return content
    
    elif instruction_format == "yaml":
        # Add JSON as YAML in frontmatter
        import yaml
        
        # Parse existing frontmatter if present
        if content.startswith("---"):
            parts = base_content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2]
            else:
                frontmatter = {}
                body = base_content
        else:
            frontmatter = {}
            body = base_content
        
        # Add JSON instructions to frontmatter
        frontmatter["json_instructions"] = json_instructions
        
        # Rebuild content
        new_content = "---\n"
        new_content += yaml.dump(frontmatter, default_flow_style=False)
        new_content += "---\n"
        new_content += body
        
        return new_content
    
    else:
        raise ValueError(f"Unknown instruction format: {instruction_format}")