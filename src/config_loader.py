"""Configuration loader and validator."""
import hashlib
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


class Config:
    """Configuration container with validation."""
    
    def __init__(self, config_dict: Dict[str, Any], config_path: str):
        self.raw = config_dict
        self.path = config_path
        self.version = config_dict.get('version', 1)
        self.defaults = config_dict.get('defaults', {})
        self.icps = config_dict.get('icps', [])
        self._validate()
    
    def _validate(self):
        """Validate required config fields."""
        if not self.icps:
            raise ValueError("Config must contain at least one ICP")
        
        for icp in self.icps:
            if 'name' not in icp:
                raise ValueError("Each ICP must have a 'name' field")
            if 'subreddit_priors' not in icp:
                raise ValueError(f"ICP '{icp['name']}' must have 'subreddit_priors'")
            if 'keyword_buckets' not in icp:
                raise ValueError(f"ICP '{icp['name']}' must have 'keyword_buckets'")
    
    def get_hash(self) -> str:
        """Generate short hash of config for tracking."""
        content = yaml.dump(self.raw, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def get_icp(self, name: str) -> Optional[Dict[str, Any]]:
        """Get ICP config by name."""
        for icp in self.icps:
            if icp['name'] == name:
                return icp
        return None
    
    def get_icps_to_run(self, icp_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of ICPs to process."""
        if icp_filter:
            icp = self.get_icp(icp_filter)
            if not icp:
                raise ValueError(f"ICP '{icp_filter}' not found in config")
            return [icp]
        return self.icps
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration."""
        return self.defaults.get('api', {})
    
    def get_filter_config(self) -> Dict[str, Any]:
        """Get filter configuration."""
        return self.defaults.get('filters', {})
    
    def get_scoring_config(self) -> Dict[str, Any]:
        """Get scoring configuration."""
        return self.defaults.get('scoring', {})
    
    def get_selection_config(self) -> Dict[str, Any]:
        """Get selection configuration."""
        return self.defaults.get('selection', {})


def load_config(config_path: str) -> Config:
    """Load and validate YAML config file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    return Config(config_dict, config_path)
