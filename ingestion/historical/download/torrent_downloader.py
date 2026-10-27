"""Discover and download monthly Reddit archives from local torrent files."""

import re
import subprocess
from pathlib import Path, PurePosixPath

FILE_PREFIX = {"submissions": "RS", "comments": "RC"}
FILE_ENTRY = re.compile(r"^\s*(\d+)\|(.+?)\s*$")


def build_archive_filename(year: int, month: int, data_type: str) -> str:
    """Build the archive name for a month and Reddit data type."""
    if type(year) is not int or not 1 <= year <= 9999:
        raise ValueError("year must be an integer between 1 and 9999")
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("month must be an integer between 1 and 12")
    if data_type not in FILE_PREFIX:
        raise ValueError("data_type must be 'submissions' or 'comments'")
    return f"{FILE_PREFIX[data_type]}_{year:04d}-{month:02d}.zst"


def inspect_torrent_files(torrent_path: Path | str) -> list[tuple[int, str]]:
    """Return (aria2 file index, internal path) entries from a torrent."""
    result = subprocess.run(
        ["aria2c", "--show-files", str(torrent_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    entries: list[tuple[int, str]] = []
    for line in result.stdout.splitlines():
        match = FILE_ENTRY.match(line)
        if match:
            entries.append((int(match.group(1)), match.group(2)))
    return entries


def find_archive_in_torrents(
    torrent_dir: Path | str, year: int, month: int, data_type: str
) -> tuple[Path, int]:
    """Find the sole torrent and aria2 index containing the requested archive."""
    if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError("year must be an integer between 1 and 9999")
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("month must be an integer between 1 and 12")
    
    archive_name = build_archive_filename(year, month, data_type)
    torrent_dir = Path(torrent_dir)
    if not torrent_dir.is_dir():
        raise FileNotFoundError(f"Torrent directory does not exist: {torrent_dir}")

    torrents = sorted(torrent_dir.rglob("*.torrent"))
    if not torrents:
        raise FileNotFoundError(f"No .torrent files found in {torrent_dir}")

    matches = [
        (torrent, index)
        for torrent in torrents
        for index, internal_path in inspect_torrent_files(torrent)
        if PurePosixPath(internal_path).name == archive_name
    ]
    if not matches:
        raise FileNotFoundError(f"Archive {archive_name} not found in torrents under {torrent_dir}")
    if len(matches) > 1:
        locations = ", ".join(f"{torrent} (index {index})" for torrent, index in matches)
        raise ValueError(f"Duplicate archive {archive_name} found in: {locations}")
    return matches[0]


def download_reddit_archive(
    torrent_dir: Path | str,
    output_dir: Path | str,
    year: int,
    month: int,
    data_type: str = "submissions",
) -> Path:
    """Download one monthly archive and return its path under output_dir."""

    archive_name = build_archive_filename(year, month, data_type)

    torrent, index = find_archive_in_torrents(torrent_dir, year, month, data_type)

    if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError("year must be an integer between 1 and 9999")
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("month must be an integer between 1 and 12")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = [
            path
            for path in output_dir.rglob(archive_name)
            if path.is_file()
        ]
    
    if len(existing) == 1:
        print(f"Archive already exists: {existing[0]}")
        return existing[0]

    if len(existing) > 1:
        raise ValueError(
            f"Multiple existing copies of {archive_name} found in {output_dir}"
        )

    subprocess.run(
        [
            "aria2c",
            f"--select-file={index}",
            "--seed-time=0",
            "--file-allocation=none",
            str(torrent),
            "-d",
            str(output_dir),
        ],
        check=True,
    )

    downloaded_files = sorted(
        path for path in output_dir.rglob(archive_name) if path.is_file()
    )
    if not downloaded_files:
        raise FileNotFoundError(f"Downloaded archive {archive_name} not found in {output_dir}")
    if len(downloaded_files) > 1:
        raise ValueError(f"Multiple downloaded copies of {archive_name} found in {output_dir}")
    return downloaded_files[0]
