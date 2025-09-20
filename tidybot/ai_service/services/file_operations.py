import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)


class FileOperationStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CONFLICT = "conflict"


class FileOperationResult:
    def __init__(
        self,
        original_path: str,
        new_path: Optional[str] = None,
        status: FileOperationStatus = FileOperationStatus.SUCCESS,
        error: Optional[str] = None,
        backup_path: Optional[str] = None
    ):
        self.original_path = original_path
        self.new_path = new_path
        self.status = status
        self.error = error
        self.backup_path = backup_path
        self.timestamp = datetime.now().isoformat()


class FileSystemOperations:
    """Service for performing actual file system operations"""

    def __init__(self):
        self.undo_history: List[FileOperationResult] = []
        self.max_undo_history = 100

    async def rename_file(
        self,
        original_path: Path,
        new_name: str,
        create_backup: bool = False,
        overwrite: bool = False
    ) -> FileOperationResult:
        """
        Rename a file on the filesystem

        Args:
            original_path: Current file path
            new_name: New file name (not full path)
            create_backup: Whether to create a backup before renaming
            overwrite: Whether to overwrite if target exists

        Returns:
            FileOperationResult with operation details
        """
        try:
            original_path = Path(original_path)
            if not original_path.exists():
                return FileOperationResult(
                    str(original_path),
                    status=FileOperationStatus.FAILED,
                    error=f"File not found: {original_path}"
                )

            # Build new path with same parent directory
            new_path = original_path.parent / new_name

            # Check if target already exists
            if new_path.exists() and not overwrite:
                return FileOperationResult(
                    str(original_path),
                    str(new_path),
                    status=FileOperationStatus.CONFLICT,
                    error=f"Target file already exists: {new_path}"
                )

            # Create backup if requested
            backup_path = None
            if create_backup:
                backup_path = await self._create_backup(original_path)

            # Perform the rename
            await asyncio.to_thread(os.rename, str(original_path), str(new_path))

            result = FileOperationResult(
                str(original_path),
                str(new_path),
                FileOperationStatus.SUCCESS,
                backup_path=str(backup_path) if backup_path else None
            )

            # Add to undo history
            self._add_to_history(result)

            logger.info(f"Successfully renamed {original_path} to {new_path}")
            return result

        except Exception as e:
            logger.error(f"Error renaming file {original_path}: {e}")
            return FileOperationResult(
                str(original_path),
                status=FileOperationStatus.FAILED,
                error=str(e)
            )

    async def batch_rename(
        self,
        rename_operations: List[Tuple[Path, str]],
        create_backup: bool = False,
        stop_on_error: bool = False
    ) -> List[FileOperationResult]:
        """
        Batch rename multiple files

        Args:
            rename_operations: List of (original_path, new_name) tuples
            create_backup: Whether to create backups
            stop_on_error: Whether to stop on first error

        Returns:
            List of FileOperationResult for each operation
        """
        results = []

        for original_path, new_name in rename_operations:
            result = await self.rename_file(
                original_path,
                new_name,
                create_backup=create_backup
            )
            results.append(result)

            if stop_on_error and result.status == FileOperationStatus.FAILED:
                logger.warning(f"Stopping batch rename due to error: {result.error}")
                break

        return results

    async def move_file(
        self,
        original_path: Path,
        target_directory: Path,
        new_name: Optional[str] = None,
        create_backup: bool = False
    ) -> FileOperationResult:
        """
        Move a file to a different directory with optional rename

        Args:
            original_path: Current file path
            target_directory: Target directory path
            new_name: Optional new name for the file
            create_backup: Whether to create a backup

        Returns:
            FileOperationResult with operation details
        """
        try:
            original_path = Path(original_path)
            target_directory = Path(target_directory)

            if not original_path.exists():
                return FileOperationResult(
                    str(original_path),
                    status=FileOperationStatus.FAILED,
                    error=f"File not found: {original_path}"
                )

            if not target_directory.exists():
                # Create target directory if it doesn't exist
                await asyncio.to_thread(target_directory.mkdir, parents=True, exist_ok=True)

            # Determine target path
            file_name = new_name if new_name else original_path.name
            target_path = target_directory / file_name

            # Create backup if requested
            backup_path = None
            if create_backup:
                backup_path = await self._create_backup(original_path)

            # Move the file
            await asyncio.to_thread(shutil.move, str(original_path), str(target_path))

            result = FileOperationResult(
                str(original_path),
                str(target_path),
                FileOperationStatus.SUCCESS,
                backup_path=str(backup_path) if backup_path else None
            )

            self._add_to_history(result)

            logger.info(f"Successfully moved {original_path} to {target_path}")
            return result

        except Exception as e:
            logger.error(f"Error moving file {original_path}: {e}")
            return FileOperationResult(
                str(original_path),
                status=FileOperationStatus.FAILED,
                error=str(e)
            )

    async def organize_files(
        self,
        files_with_folders: List[Tuple[Path, str]],
        base_directory: Path,
        create_backup: bool = False
    ) -> List[FileOperationResult]:
        """
        Organize multiple files into suggested folders

        Args:
            files_with_folders: List of (file_path, suggested_folder) tuples
            base_directory: Base directory for organization
            create_backup: Whether to create backups

        Returns:
            List of FileOperationResult for each operation
        """
        results = []
        base_directory = Path(base_directory)

        for file_path, folder_name in files_with_folders:
            target_directory = base_directory / folder_name
            result = await self.move_file(
                file_path,
                target_directory,
                create_backup=create_backup
            )
            results.append(result)

        return results

    async def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of a file before modification"""
        backup_dir = file_path.parent / ".tidybot_backups"
        await asyncio.to_thread(backup_dir.mkdir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name

        await asyncio.to_thread(shutil.copy2, str(file_path), str(backup_path))
        logger.info(f"Created backup: {backup_path}")

        return backup_path

    def _add_to_history(self, result: FileOperationResult):
        """Add operation to undo history"""
        self.undo_history.append(result)
        if len(self.undo_history) > self.max_undo_history:
            self.undo_history.pop(0)

    async def undo_last_operation(self) -> Optional[FileOperationResult]:
        """Undo the last file operation"""
        if not self.undo_history:
            return None

        last_operation = self.undo_history.pop()

        if last_operation.status != FileOperationStatus.SUCCESS:
            return None

        try:
            # Reverse the operation
            if last_operation.new_path and Path(last_operation.new_path).exists():
                await asyncio.to_thread(
                    os.rename,
                    last_operation.new_path,
                    last_operation.original_path
                )
                logger.info(f"Undone: {last_operation.new_path} -> {last_operation.original_path}")

                return FileOperationResult(
                    last_operation.new_path,
                    last_operation.original_path,
                    FileOperationStatus.SUCCESS
                )
        except Exception as e:
            logger.error(f"Error undoing operation: {e}")
            return FileOperationResult(
                last_operation.new_path,
                status=FileOperationStatus.FAILED,
                error=str(e)
            )

        return None

    async def validate_rename_operations(
        self,
        rename_operations: List[Tuple[Path, str]]
    ) -> Dict[str, Any]:
        """
        Validate rename operations before executing

        Args:
            rename_operations: List of (original_path, new_name) tuples

        Returns:
            Validation results with conflicts and errors
        """
        validation = {
            "valid": True,
            "conflicts": [],
            "errors": [],
            "warnings": []
        }

        new_paths = set()

        for original_path, new_name in rename_operations:
            original_path = Path(original_path)

            # Check if source exists
            if not original_path.exists():
                validation["errors"].append({
                    "file": str(original_path),
                    "error": "File does not exist"
                })
                validation["valid"] = False
                continue

            # Check for duplicate targets in batch
            new_path = original_path.parent / new_name
            if str(new_path) in new_paths:
                validation["conflicts"].append({
                    "file": str(original_path),
                    "target": str(new_path),
                    "error": "Duplicate target name in batch"
                })
                validation["valid"] = False
            new_paths.add(str(new_path))

            # Check if target already exists
            if new_path.exists():
                validation["warnings"].append({
                    "file": str(original_path),
                    "target": str(new_path),
                    "warning": "Target file already exists"
                })

        return validation