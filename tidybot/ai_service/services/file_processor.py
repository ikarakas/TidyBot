from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import logging
import time
from datetime import datetime
import hashlib

from .image_analyzer import ImageAnalyzer
from .document_analyzer import DocumentAnalyzer
from .naming_engine import SmartNamingEngine, NamingRule
from .organization_engine import OrganizationEngine
from .file_operations import FileSystemOperations, FileOperationResult

logger = logging.getLogger(__name__)


class FileProcessor:
    def __init__(self):
        self.image_analyzer = ImageAnalyzer()
        self.document_analyzer = DocumentAnalyzer()
        self.naming_engine = SmartNamingEngine()
        self.organization_engine = OrganizationEngine()
        self.file_operations = FileSystemOperations()
        self.indexing_service = None  # Will be injected to avoid circular import
        self._cache = {}
    
    async def process_file(
        self,
        file_path: Path,
        naming_rule: Optional[NamingRule] = None,
        organize: bool = True,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        
        start_time = time.time()
        
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_hash = None
            if use_cache:
                file_hash = await self._get_file_hash(file_path)
                if file_hash in self._cache:
                    logger.info(f"Using cached result for {file_path}")
                    return self._cache[file_hash]
            
            result = {
                'original_path': str(file_path),
                'original_name': file_path.name,
                'file_size': file_path.stat().st_size,
                'processed_at': datetime.now().isoformat(),
                'status': 'processing'
            }
            
            analysis_result = await self._analyze_file(file_path)
            result['analysis'] = analysis_result
            
            new_name, confidence = await self.naming_engine.generate_name(
                file_path, 
                analysis_result, 
                naming_rule
            )
            result['suggested_name'] = new_name
            result['confidence_score'] = confidence
            
            alternative_names = await self.naming_engine.suggest_alternatives(
                file_path,
                analysis_result,
                num_suggestions=3
            )
            result['alternative_names'] = alternative_names
            
            if organize:
                organization_result = await self.organization_engine.suggest_organization(
                    file_path, 
                    analysis_result
                )
                result['organization'] = organization_result
            
            processing_time = (time.time() - start_time) * 1000
            result['processing_time_ms'] = int(processing_time)
            result['status'] = 'completed'
            
            if use_cache and file_hash:
                self._cache[file_hash] = result
            
            logger.info(f"Processed {file_path} in {processing_time:.2f}ms")
            return result
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return {
                'original_path': str(file_path),
                'original_name': file_path.name if file_path else 'unknown',
                'status': 'failed',
                'error': str(e),
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
    
    async def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        mime_type = self._get_mime_type(file_path)
        
        if mime_type.startswith('image/'):
            return await self.image_analyzer.analyze(file_path)
        elif mime_type.startswith('application/') or mime_type.startswith('text/'):
            return await self.document_analyzer.analyze(file_path)
        else:
            return {
                'type': 'unknown',
                'mime_type': mime_type,
                'extension': file_path.suffix
            }
    
    def _get_mime_type(self, file_path: Path) -> str:
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'
    
    async def _get_file_hash(self, file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def batch_process(
        self,
        file_paths: list[Path],
        naming_rule: Optional[NamingRule] = None,
        organize: bool = True
    ) -> list[Dict[str, Any]]:
        
        results = []
        
        for file_path in file_paths:
            result = await self.process_file(file_path, naming_rule, organize)
            results.append(result)
        
        return results
    
    def clear_cache(self):
        self._cache.clear()
        logger.info("File processor cache cleared")

    async def apply_rename(
        self,
        file_path: Path,
        new_name: str,
        create_backup: bool = True,
        update_index: bool = True
    ) -> FileOperationResult:
        """
        Apply the rename operation to the actual file

        Args:
            file_path: Current file path
            new_name: New name for the file
            create_backup: Whether to create backup before renaming
            update_index: Whether to update the search index

        Returns:
            FileOperationResult with operation details
        """
        result = await self.file_operations.rename_file(
            file_path,
            new_name,
            create_backup=create_backup
        )

        if result.status.value == "success" and update_index and self.indexing_service:
            await self.indexing_service.update_renamed_file(
                result.original_path,
                result.new_path
            )

        return result

    async def apply_batch_rename(
        self,
        rename_operations: List[Tuple[Path, str]],
        create_backup: bool = True,
        validate_first: bool = True
    ) -> Dict[str, Any]:
        """
        Apply batch rename operations with validation

        Args:
            rename_operations: List of (original_path, new_name) tuples
            create_backup: Whether to create backups
            validate_first: Whether to validate before executing

        Returns:
            Dictionary with results and any errors
        """
        if validate_first:
            validation = await self.file_operations.validate_rename_operations(
                rename_operations
            )
            if not validation["valid"]:
                return {
                    "success": False,
                    "validation": validation,
                    "results": []
                }

        results = await self.file_operations.batch_rename(
            rename_operations,
            create_backup=create_backup
        )

        # Update index for successful renames
        if self.indexing_service:
            for result in results:
                if result.status.value == "success":
                    await self.indexing_service.update_renamed_file(
                        result.original_path,
                        result.new_path
                    )

        return {
            "success": True,
            "results": [
                {
                    "original_path": r.original_path,
                    "new_path": r.new_path,
                    "status": r.status.value,
                    "error": r.error,
                    "backup_path": r.backup_path
                }
                for r in results
            ]
        }

    async def organize_and_rename(
        self,
        file_path: Path,
        base_directory: Optional[Path] = None,
        apply_changes: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze, suggest organization and renaming, optionally apply

        Args:
            file_path: File to process
            base_directory: Base directory for organization
            apply_changes: Whether to apply the changes

        Returns:
            Dictionary with analysis, suggestions, and results if applied
        """
        # Process the file to get suggestions
        process_result = await self.process_file(file_path)

        response = {
            "analysis": process_result.get("analysis"),
            "suggested_name": process_result.get("suggested_name"),
            "confidence_score": process_result.get("confidence_score"),
            "organization": process_result.get("organization"),
            "applied": False
        }

        if apply_changes and process_result.get("status") == "completed":
            # Apply rename if suggested
            if process_result.get("suggested_name"):
                rename_result = await self.apply_rename(
                    file_path,
                    process_result["suggested_name"]
                )
                response["rename_result"] = {
                    "success": rename_result.status.value == "success",
                    "new_path": rename_result.new_path,
                    "error": rename_result.error
                }

                # Update file path if rename was successful
                if rename_result.new_path:
                    file_path = Path(rename_result.new_path)

            # Apply organization if suggested
            if process_result.get("organization") and base_directory:
                folder = process_result["organization"].get("suggested_folder")
                if folder:
                    move_result = await self.file_operations.move_file(
                        file_path,
                        Path(base_directory) / folder
                    )
                    response["organization_result"] = {
                        "success": move_result.status.value == "success",
                        "new_path": move_result.new_path,
                        "error": move_result.error
                    }

            response["applied"] = True

        return response