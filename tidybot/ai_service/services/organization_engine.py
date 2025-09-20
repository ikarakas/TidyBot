from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class OrganizationStrategy(Enum):
    BY_TYPE = "by_type"
    BY_DATE = "by_date"
    BY_PROJECT = "by_project"
    BY_CATEGORY = "by_category"
    CUSTOM = "custom"


@dataclass
class OrganizationRule:
    strategy: OrganizationStrategy
    base_path: Path
    create_subfolders: bool = True
    date_format: str = "%Y/%m"
    type_mapping: Dict[str, str] = None
    category_mapping: Dict[str, str] = None
    
    def __post_init__(self):
        if self.type_mapping is None:
            self.type_mapping = {
                'image': 'Images',
                'document': 'Documents',
                'spreadsheet': 'Spreadsheets',
                'presentation': 'Presentations',
                'video': 'Videos',
                'audio': 'Audio',
                'archive': 'Archives',
                'code': 'Code',
                'screenshot': 'Screenshots'
            }
        
        if self.category_mapping is None:
            self.category_mapping = {
                'invoice': 'Financial/Invoices',
                'report': 'Reports',
                'contract': 'Legal/Contracts',
                'resume': 'HR/Resumes',
                'photo': 'Photos',
                'email': 'Correspondence'
            }


class OrganizationEngine:
    def __init__(self):
        self.default_rules = {
            OrganizationStrategy.BY_TYPE: OrganizationRule(
                strategy=OrganizationStrategy.BY_TYPE,
                base_path=Path.home() / "Documents" / "TidyBot"
            ),
            OrganizationStrategy.BY_DATE: OrganizationRule(
                strategy=OrganizationStrategy.BY_DATE,
                base_path=Path.home() / "Documents" / "TidyBot",
                date_format="%Y/%B"
            ),
            OrganizationStrategy.BY_CATEGORY: OrganizationRule(
                strategy=OrganizationStrategy.BY_CATEGORY,
                base_path=Path.home() / "Documents" / "TidyBot"
            )
        }
        
        self.project_patterns = {
            'project_alpha': ['alpha', 'project-a', 'proj_a'],
            'project_beta': ['beta', 'project-b', 'proj_b'],
            'client_work': ['client', 'customer', 'contract'],
            'personal': ['personal', 'private', 'my_'],
            'work': ['work', 'office', 'company']
        }
    
    async def suggest_organization(
        self,
        file_path: Path,
        analysis_result: Dict[str, Any],
        rule: Optional[OrganizationRule] = None
    ) -> Dict[str, Any]:
        
        try:
            if not rule:
                rule = self._determine_best_strategy(file_path, analysis_result)
            
            suggested_path = await self._generate_path(file_path, analysis_result, rule)
            
            organization_result = {
                'strategy': rule.strategy.value,
                'suggested_path': str(suggested_path),
                'suggested_folder': str(suggested_path.parent),
                'create_folders': rule.create_subfolders,
                'confidence': self._calculate_confidence(analysis_result, suggested_path),
                'alternatives': await self._generate_alternatives(file_path, analysis_result)
            }
            
            return organization_result
            
        except Exception as e:
            logger.error(f"Error suggesting organization for {file_path}: {e}")
            return {
                'strategy': 'none',
                'suggested_path': str(file_path),
                'error': str(e)
            }
    
    def _determine_best_strategy(
        self,
        file_path: Path,
        analysis_result: Dict[str, Any]
    ) -> OrganizationRule:
        
        file_type = analysis_result.get('type', 'unknown')
        
        if file_type == 'image' and analysis_result.get('is_screenshot'):
            return OrganizationRule(
                strategy=OrganizationStrategy.BY_CATEGORY,
                base_path=Path.home() / "Documents" / "Screenshots"
            )
        
        if 'metadata' in analysis_result:
            metadata = analysis_result['metadata']
            if metadata.get('DateTime') or metadata.get('DateTimeOriginal'):
                return self.default_rules[OrganizationStrategy.BY_DATE]
        
        category = self._determine_category(analysis_result)
        if category in ['invoice', 'report', 'contract', 'resume']:
            return self.default_rules[OrganizationStrategy.BY_CATEGORY]
        
        project = self._detect_project(file_path, analysis_result)
        if project:
            return OrganizationRule(
                strategy=OrganizationStrategy.BY_PROJECT,
                base_path=Path.home() / "Documents" / "Projects" / project
            )
        
        return self.default_rules[OrganizationStrategy.BY_TYPE]
    
    async def _generate_path(
        self,
        file_path: Path,
        analysis_result: Dict[str, Any],
        rule: OrganizationRule
    ) -> Path:
        
        base_path = rule.base_path
        
        if rule.strategy == OrganizationStrategy.BY_TYPE:
            file_type = self._get_file_type(analysis_result)
            folder_name = rule.type_mapping.get(file_type, 'Other')
            target_path = base_path / folder_name
            
        elif rule.strategy == OrganizationStrategy.BY_DATE:
            date = self._extract_date(file_path, analysis_result)
            date_folder = date.strftime(rule.date_format)
            target_path = base_path / date_folder
            
        elif rule.strategy == OrganizationStrategy.BY_CATEGORY:
            category = self._determine_category(analysis_result)
            folder_path = rule.category_mapping.get(category, 'Uncategorized')
            target_path = base_path / folder_path
            
        elif rule.strategy == OrganizationStrategy.BY_PROJECT:
            project = self._detect_project(file_path, analysis_result)
            target_path = base_path / (project or 'General')
            
        else:
            target_path = base_path
        
        new_filename = analysis_result.get('suggested_name', file_path.name)
        if 'suggested_name' not in analysis_result:
            new_filename = file_path.name
        
        return target_path / new_filename
    
    def _get_file_type(self, analysis_result: Dict[str, Any]) -> str:
        file_type = analysis_result.get('type', 'unknown')
        
        if file_type == 'image' and analysis_result.get('is_screenshot'):
            return 'screenshot'
        
        if file_type == 'document':
            format_type = analysis_result.get('format', '').lower()
            if 'excel' in format_type or 'spreadsheet' in format_type:
                return 'spreadsheet'
            elif 'powerpoint' in format_type or 'presentation' in format_type:
                return 'presentation'
        
        return file_type
    
    def _determine_category(self, analysis_result: Dict[str, Any]) -> str:
        text_content = ''
        
        if 'text' in analysis_result:
            text_content = analysis_result['text'].lower()
        elif 'ocr_text' in analysis_result:
            text_content = analysis_result['ocr_text'].lower()
        
        keywords = analysis_result.get('keywords', [])
        if keywords:
            text_content += ' ' + ' '.join(keywords).lower()
        
        category_keywords = {
            'invoice': ['invoice', 'bill', 'payment', 'receipt', 'amount due'],
            'report': ['report', 'analysis', 'summary', 'findings', 'conclusion'],
            'contract': ['contract', 'agreement', 'terms', 'conditions', 'party'],
            'resume': ['resume', 'cv', 'experience', 'education', 'skills'],
            'email': ['from:', 'to:', 'subject:', 're:', 'fw:'],
            'photo': ['exif', 'camera', 'lens', 'exposure']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text_content for keyword in keywords):
                return category
        
        return 'general'
    
    def _detect_project(self, file_path: Path, analysis_result: Dict[str, Any]) -> Optional[str]:
        search_text = file_path.name.lower()
        
        if 'text' in analysis_result:
            search_text += ' ' + analysis_result['text'].lower()[:500]
        
        if 'keywords' in analysis_result:
            search_text += ' ' + ' '.join(analysis_result['keywords']).lower()
        
        for project, patterns in self.project_patterns.items():
            if any(pattern in search_text for pattern in patterns):
                return project
        
        return None
    
    def _extract_date(self, file_path: Path, analysis_result: Dict[str, Any]) -> datetime:
        if 'metadata' in analysis_result:
            metadata = analysis_result['metadata']
            
            date_fields = ['DateTime', 'DateTimeOriginal', 'created', 'modified']
            for field in date_fields:
                if field in metadata and metadata[field]:
                    try:
                        if isinstance(metadata[field], str):
                            return datetime.fromisoformat(metadata[field].replace('Z', '+00:00'))
                    except:
                        pass
        
        if 'dates' in analysis_result and analysis_result['dates']:
            try:
                date_str = analysis_result['dates'][0]
                return self._parse_date_string(date_str)
            except:
                pass
        
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    
    def _parse_date_string(self, date_str: str) -> datetime:
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y:%m:%d %H:%M:%S"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        raise ValueError(f"Could not parse date: {date_str}")
    
    def _calculate_confidence(self, analysis_result: Dict[str, Any], suggested_path: Path) -> float:
        confidence = 0.5
        
        if 'error' in analysis_result:
            return 0.1
        
        if self._determine_category(analysis_result) != 'general':
            confidence += 0.2
        
        if self._detect_project(suggested_path, analysis_result):
            confidence += 0.15
        
        if 'metadata' in analysis_result and analysis_result['metadata']:
            confidence += 0.1
        
        if 'keywords' in analysis_result and len(analysis_result['keywords']) > 3:
            confidence += 0.15
        
        return min(1.0, confidence)
    
    async def _generate_alternatives(
        self,
        file_path: Path,
        analysis_result: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        
        alternatives = []
        
        strategies = [
            OrganizationStrategy.BY_TYPE,
            OrganizationStrategy.BY_DATE,
            OrganizationStrategy.BY_CATEGORY
        ]
        
        for strategy in strategies:
            try:
                rule = self.default_rules.get(strategy, OrganizationRule(strategy=strategy, base_path=Path.home() / "Documents"))
                path = await self._generate_path(file_path, analysis_result, rule)
                alternatives.append({
                    'strategy': strategy.value,
                    'path': str(path),
                    'folder': str(path.parent)
                })
            except:
                continue
        
        return alternatives