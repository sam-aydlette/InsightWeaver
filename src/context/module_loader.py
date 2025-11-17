"""
Context Module Loader
Loads and manages domain knowledge modules from config files
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContextModule:
    """Represents a loaded context module"""
    name: str
    description: str
    content: str  # Formatted content ready for Claude
    priority: str  # high, medium, low
    token_estimate: int
    module_type: str  # domain_knowledge, supplemental, historical
    last_updated: str


class ContextModuleLoader:
    """Loads and formats context modules for inclusion in Claude prompts"""

    def __init__(self, modules_dir: str = "config/context_modules"):
        """
        Initialize module loader

        Args:
            modules_dir: Path to context modules directory
        """
        self.modules_dir = Path(modules_dir)
        self.loaded_modules: Dict[str, ContextModule] = {}

    def load_all_modules(self) -> Dict[str, List[ContextModule]]:
        """
        Load all context modules from directory structure

        Returns:
            Dictionary organized by module type
        """
        modules_by_type = {
            'domain_knowledge': [],
            'supplemental': [],
            'historical': [],
            'core': []
        }

        if not self.modules_dir.exists():
            logger.warning(f"Modules directory not found: {self.modules_dir}")
            return modules_by_type

        # Load from each subdirectory
        for module_type in modules_by_type.keys():
            type_dir = self.modules_dir / module_type
            if type_dir.exists():
                modules = self._load_modules_from_directory(type_dir, module_type)
                modules_by_type[module_type] = modules
                logger.info(f"Loaded {len(modules)} {module_type} modules")

        return modules_by_type

    def _load_modules_from_directory(
        self,
        directory: Path,
        module_type: str
    ) -> List[ContextModule]:
        """Load all JSON modules from a directory"""
        modules = []

        for json_file in directory.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                module = self._parse_module(data, module_type)
                modules.append(module)
                self.loaded_modules[module.name] = module

            except Exception as e:
                logger.error(f"Failed to load module {json_file}: {e}")

        return modules

    def _parse_module(self, data: Dict[str, Any], module_type: str) -> ContextModule:
        """Parse module JSON into ContextModule object"""
        # Format content for Claude
        formatted_content = self._format_module_content(data)

        return ContextModule(
            name=data.get('module_name', 'unknown'),
            description=data.get('description', ''),
            content=formatted_content,
            priority=data.get('priority', 'medium'),
            token_estimate=data.get('token_estimate', 0),
            module_type=module_type,
            last_updated=data.get('last_updated', 'unknown')
        )

    def _format_module_content(self, data: Dict[str, Any]) -> str:
        """Format module data into readable context for Claude"""
        parts = []

        # Module header
        parts.append(f"## {data.get('module_name', 'Module')}")
        if 'description' in data:
            parts.append(f"{data['description']}\n")

        # Content sections
        if 'content_sections' in data:
            for section_name, section_data in data['content_sections'].items():
                parts.append(f"\n### {section_name.replace('_', ' ').title()}")

                if isinstance(section_data, dict):
                    if 'description' in section_data:
                        parts.append(section_data['description'])
                    if 'content' in section_data:
                        content = section_data['content']
                        if isinstance(content, list):
                            for item in content:
                                parts.append(f"• {item}")
                        elif isinstance(content, str):
                            parts.append(content)
                elif isinstance(section_data, list):
                    for item in section_data:
                        parts.append(f"• {item}")
                elif isinstance(section_data, str):
                    parts.append(section_data)

        # Key metrics (if present)
        if 'key_metrics_baselines' in data:
            parts.append("\n### Key Metrics (Baseline)")
            for category, metrics in data['key_metrics_baselines'].items():
                parts.append(f"\n**{category.title()}:**")
                for metric, value in metrics.items():
                    parts.append(f"• {metric.replace('_', ' ').title()}: {value}")

        return "\n".join(parts)

    def get_modules_by_priority(
        self,
        modules: List[ContextModule],
        priority: str = 'high'
    ) -> List[ContextModule]:
        """Filter modules by priority level"""
        return [m for m in modules if m.priority == priority]

    def estimate_total_tokens(self, modules: List[ContextModule]) -> int:
        """Estimate total tokens for a list of modules"""
        return sum(m.token_estimate for m in modules)

    def format_for_claude_context(
        self,
        modules: List[ContextModule],
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Format modules for inclusion in Claude context

        Args:
            modules: List of modules to include
            max_tokens: Maximum tokens to use (will prioritize by priority)

        Returns:
            Formatted string for Claude context
        """
        if not modules:
            return ""

        # Sort by priority (high -> medium -> low)
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_modules = sorted(
            modules,
            key=lambda m: priority_order.get(m.priority, 3)
        )

        # Apply token budget if specified
        if max_tokens:
            selected_modules = []
            total_tokens = 0

            for module in sorted_modules:
                if total_tokens + module.token_estimate <= max_tokens:
                    selected_modules.append(module)
                    total_tokens += module.token_estimate
                else:
                    logger.info(f"Skipping module {module.name} to stay within token budget")

            modules = selected_modules

        # Format with XML tags for Claude
        parts = ["<domain_knowledge>"]

        for module in modules:
            parts.append(f"\n{module.content}\n")

        parts.append("</domain_knowledge>")

        return "\n".join(parts)

    def get_module_by_name(self, name: str) -> Optional[ContextModule]:
        """Retrieve a specific module by name"""
        return self.loaded_modules.get(name)

    def get_module_summary(self) -> Dict[str, Any]:
        """Get summary of all loaded modules"""
        summary = {
            'total_modules': len(self.loaded_modules),
            'by_type': {},
            'by_priority': {'high': 0, 'medium': 0, 'low': 0},
            'total_tokens': 0
        }

        for module in self.loaded_modules.values():
            # Count by type
            summary['by_type'][module.module_type] = \
                summary['by_type'].get(module.module_type, 0) + 1

            # Count by priority
            if module.priority in summary['by_priority']:
                summary['by_priority'][module.priority] += 1

            # Sum tokens
            summary['total_tokens'] += module.token_estimate

        return summary
