"""
Historical Reddit Dump Downloader (Academic Torrents / ArcticShift .zst Archives).
"""
import subprocess
from pathlib import Path
from typing import List, Optional
from config.pipeline_config import StorageConfig


def download_academic_torrent(
    torrent_path: Path | str,
    output_dir: Optional[Path | str] = None,
    select_file_index: int = 2
) -> List[Path]:
    """
    Download Reddit historical submission/comment .zst dumps via aria2c.
    """
    cfg = StorageConfig()
    target_dir = Path(output_dir) if output_dir else cfg.raw_local_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "aria2c",
        f"--select-file={select_file_index}",
        "--seed-time=0",
        "--file-allocation=none",
        str(torrent_path),
        "-d",
        str(target_dir)
    ]
    subprocess.run(cmd, check=True)
    return list(target_dir.rglob("*.zst"))
