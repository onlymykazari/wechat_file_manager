import os
import re
import hashlib
from pathlib import Path
import shutil
from collections import defaultdict
import yaml
from datetime import datetime
import sqlite3
from typing import List, Tuple
from tqdm import tqdm
import argparse

def wfm_init():
    """Initialize WeChat File Manager folders and configuration"""
    default_config_path = Path(__file__).parent / 'config.yaml'
    config_path = Path.home() / 'config_wechat_file_manager.yaml'
    
    if not config_path.exists():
        shutil.copy2(default_config_path, config_path)
        print(f"Created configuration file at: {config_path}")
    else:
        print(f"Configuration file already exists at: {config_path}")
    
    # Load config to create storage directory
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    storage_path = Path(config['paths']['storage']).expanduser()
    storage_path.mkdir(parents=True, exist_ok=True)
    print(f"Storage directory ready at: {storage_path}")

class WeChatFileManager:
    """
    A class to manage WeChat files by deduplicating and organizing them efficiently.
    
    This class scans WeChat directories for media files, identifies duplicates using MD5 hashes,
    and creates a centralized storage with symbolic links to save disk space.
    """

    def __init__(self, config_path):
        """
        Initialize the WeChat file manager.

        Args:
            config_path (str or Path): Path to the YAML configuration file
        """
        self.config_path = config_path
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize paths and storage
        self.storage_path = Path(self.config['paths']['storage']).expanduser()
        self.db_path = self.storage_path / 'file_hashes.db'
        self.last_run = self.config.get('state', {}).get('last_run')
        settings = self.config.get('settings', {})
        self.min_file_size = settings.get('min_file_size', 0)
        self.skip_patterns = settings.get('skip_patterns', [])
        self.preserve_originals = settings.get('preserve_originals', True)
        self.sources = self._load_sources()
        self.init_database()
        self.file_hashes = defaultdict(list)
        self.db_conn = sqlite3.connect(self.db_path)  # Create persistent connection

    def _load_sources(self):
        """Load data sources from config, supporting legacy single-path configs.

        Each source is a dict with: name, root (Path), target_folders,
        min_file_size (MB, falls back to the global setting).
        """
        sources = self.config.get('sources')
        if not sources:
            # Backward compatibility: old configs used paths.wechat + settings.target_folders
            legacy_root = self.config.get('paths', {}).get('wechat')
            if not legacy_root:
                raise ValueError("No 'sources' defined in configuration")
            sources = [{
                'name': '',
                'root': legacy_root,
                'target_folders': self.config.get('settings', {}).get('target_folders',
                                                                      ['msg/file', 'msg/video']),
            }]
        
        normalized = []
        for src in sources:
            normalized.append({
                'name': src.get('name', ''),
                'root': Path(src['root']).expanduser(),
                'target_folders': src.get('target_folders', []),
                'min_file_size': src.get('min_file_size', self.min_file_size) * 1024 * 1024,
            })
        return normalized

    def __del__(self):
        """Cleanup database connection when object is destroyed"""
        if hasattr(self, 'db_conn'):
            self.db_conn.close()

    def init_database(self):
        """Initialize SQLite database for file hashes"""
        # Create storage directory if it doesn't exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS file_hashes (
                    hash TEXT,
                    file_path TEXT,
                    mtime FLOAT,
                    PRIMARY KEY (hash, file_path)
                )
            ''')

    def load_existing_hashes(self) -> List[Tuple[str, Path, float]]:
        """Load existing hashes from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT hash, file_path, mtime FROM file_hashes')
            return [(row[0], Path(row[1]), row[2]) for row in cursor.fetchall()]

    def save_file_hash(self, file_hash: str, file_path: Path):
        """Save file hash to database"""
        mtime = file_path.stat().st_mtime
        self.db_conn.execute(
            'INSERT OR REPLACE INTO file_hashes (hash, file_path, mtime) VALUES (?, ?, ?)',
            (file_hash, str(file_path), mtime)
        )
        self.db_conn.commit()  # Commit changes periodically

    def should_process_file(self, file_path, min_file_size):
        try:
            stat = file_path.stat()

            # Check file size requirement
            if stat.st_size < min_file_size:
                return False

            # Only process files modified after the last run.
            # WeChat 4.x stores files in per-month subfolders, so directory
            # mtime is unreliable; compare against each file's mtime instead.
            if self.last_run:
                try:
                    last_run_time = datetime.fromisoformat(self.last_run)
                    if datetime.fromtimestamp(stat.st_mtime) <= last_run_time:
                        return False
                except ValueError:
                    pass

            # Skip files matching any of the patterns
            for pattern in self.skip_patterns:
                if pattern in file_path.name:
                    return False

            return True
        except OSError:
            return False

    def clean_filename(self, filename: str, file_hash: str) -> str:
        """Remove duplicate indicators and append hash prefix to filename"""
        base_name = re.sub(r' \(\d+\)(?=\.[^.]+$)', '', filename)
        stem, dot, ext = base_name.rpartition('.')
        if not stem:
            return f"{base_name}_{file_hash[:5]}"
        return f"{stem}_{file_hash[:5]}.{ext}"

    def process_files(self):
        self.storage_path.mkdir(parents=True, exist_ok=True)

        for source in self.sources:
            if not source['root'].exists():
                print(f"Skipping source '{source['name'] or 'default'}': path not found: {source['root']}")
                continue
            self.process_source(source)

    def process_source(self, source):
        # Each source stores files under its own subdirectory to avoid collisions
        source_storage = self.storage_path / source['name'] if source['name'] else self.storage_path

        # Get list of valid user directories first
        user_dirs = [d for d in source['root'].iterdir() if d.is_dir()]
        
        desc = f"Processing {source['name'] or 'WeChat'} users"
        for user_dir in tqdm(user_dirs, desc=desc):
            for target in source['target_folders']:
                target_dir = user_dir / target
                if not target_dir.exists():
                    continue
                
                storage_target_dir = source_storage / target
                storage_target_dir.mkdir(parents=True, exist_ok=True)
                
                for file_path in target_dir.rglob('*'):
                    if file_path.is_file() and not file_path.is_symlink() and self.should_process_file(file_path, source['min_file_size']):
                        file_hash = self.calculate_md5(file_path)
                        
                        # Check if this hash already exists in database
                        cursor = self.db_conn.execute('SELECT file_path FROM file_hashes WHERE hash = ? AND file_path LIKE ?',
                                                    (file_hash, str(self.storage_path) + '%'))
                        stored_file = cursor.fetchone()
                        
                        if stored_file and Path(stored_file[0]).exists():
                            new_path = Path(stored_file[0])
                        else:
                            clean_name = self.clean_filename(file_path.name, file_hash)
                            new_path = storage_target_dir / clean_name
                            # print the new file path 
                            print(f"Added: {new_path}")
                            if self.preserve_originals:
                                shutil.copy2(str(file_path), str(new_path))
                            else:
                                shutil.move(str(file_path), str(new_path))
                            # Record the storage copy so future duplicates are detected
                            self.save_file_hash(file_hash, new_path)
                        
                        if not self.preserve_originals:
                            if file_path.exists():
                                file_path.unlink()
                            os.symlink(str(new_path), str(file_path))
                        
                        self.save_file_hash(file_hash, file_path)

    def update_last_run(self):
        """Update the last run timestamp in config file"""
        self.config['state'] = self.config.get('state', {})
        self.config['state']['last_run'] = datetime.now().isoformat()
        
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(self.config, f, allow_unicode=True)

    def calculate_md5(self, file_path: Path) -> str:
        """Calculate MD5 hash of a file."""
        return hashlib.md5(file_path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='WeChat File Manager')
    parser.add_argument('command', choices=['init', 'run'], help='Command to execute')
    args = parser.parse_args()
    
    if args.command == 'init':
        wfm_init()
    elif args.command == 'run':
        config_path = Path.home() / 'config_wechat_file_manager.yaml'
        if not config_path.exists():
            print("Configuration not found. Please run 'wfm init' first.")
            return
        
        manager = WeChatFileManager(config_path)
        manager.process_files()
        manager.update_last_run()

if __name__ == "__main__":
    main()
