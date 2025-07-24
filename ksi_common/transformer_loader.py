"""
Service Transformer Loading Utility

Provides a simple way for services to load their transformers from
var/lib/transformers/services/ during startup.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("transformer_loader", version="1.0.0")


async def load_service_transformers(
    service_name: str,
    transformer_file: str,
    event_emitter: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Load transformers for a service from var/lib/transformers/services/.
    
    Args:
        service_name: Name of the service loading transformers (for logging)
        transformer_file: Name of the YAML file (without path)
        event_emitter: Event emitter function for router:register_transformer
        
    Returns:
        Status dict with loaded transformer count and any errors
    """
    if not event_emitter:
        return {
            "status": "error",
            "error": "No event emitter available",
            "loaded": 0
        }
    
    # Construct path to transformer file
    transformers_dir = Path("var/lib/transformers/services")
    file_path = transformers_dir / transformer_file
    
    if not file_path.exists():
        logger.warning(f"Transformer file not found: {file_path}")
        return {
            "status": "not_found",
            "file": str(file_path),
            "loaded": 0
        }
    
    try:
        # Load YAML file
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if not config or 'transformers' not in config:
            logger.warning(f"No transformers found in {file_path}")
            return {
                "status": "empty",
                "file": str(file_path),
                "loaded": 0
            }
        
        # Register each transformer
        loaded = 0
        errors = []
        
        for transformer in config['transformers']:
            try:
                # Register via router:register_transformer event
                result = await event_emitter("router:register_transformer", {
                    "transformer": transformer
                })
                
                # Check result
                if result and isinstance(result, list):
                    result = result[0] if result else {}
                
                if result.get('status') == 'registered':
                    loaded += 1
                    logger.debug(f"Registered transformer: {transformer.get('name', 'unnamed')} "
                               f"({transformer.get('source')} -> {transformer.get('target')})")
                else:
                    errors.append(f"Failed to register {transformer.get('name', 'unnamed')}: {result}")
                    
            except Exception as e:
                errors.append(f"Error registering transformer: {e}")
                logger.error(f"Failed to register transformer from {file_path}: {e}")
        
        # Log summary
        logger.info(f"Service '{service_name}' loaded {loaded} transformers from {transformer_file}")
        
        return {
            "status": "success",
            "file": str(file_path),
            "loaded": loaded,
            "total": len(config['transformers']),
            "errors": errors if errors else None
        }
        
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in {file_path}: {e}")
        return {
            "status": "error",
            "error": f"Invalid YAML: {e}",
            "file": str(file_path),
            "loaded": 0
        }
    except Exception as e:
        logger.error(f"Failed to load transformers from {file_path}: {e}")
        return {
            "status": "error", 
            "error": str(e),
            "file": str(file_path),
            "loaded": 0
        }