"""Tests for monthly archive discovery and download without aria2 or network."""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from ingestion.historical.download.torrent_downloader import (
    build_archive_filename,
    download_reddit_archive,
    find_archive_in_torrents,
    inspect_torrent_files,
)


def test_duplicate_archive_in_multiple_torrents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    torrent_dir = tmp_path / "torrents"
    torrent_dir.mkdir()

    first = torrent_dir / "first.torrent"
    second = torrent_dir / "second.torrent"
    first.touch()
    second.touch()

    run = Mock(side_effect=[
        subprocess.CompletedProcess(
            ["aria2c"],
            0,
            stdout="2|./RS_2026-07.zst\n",
        ),
        subprocess.CompletedProcess(
            ["aria2c"],
            0,
            stdout="5|./reddit/RS_2026-07.zst\n",
        ),
    ])
    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(
        ValueError,
        match="Duplicate archive RS_2026-07.zst",
    ) as error:
        find_archive_in_torrents(
            torrent_dir,
            2026,
            7,
            "submissions",
        )

    assert str(first) in str(error.value)
    assert str(second) in str(error.value)
    assert run.call_count == 2


@pytest.mark.parametrize("month", [0, 13])
def test_invalid_month(month: int) -> None:
    with pytest.raises(ValueError, match="month"):
        build_archive_filename(2026, month, "submissions")


def test_invalid_data_type() -> None:
    with pytest.raises(ValueError, match="data_type"):
        build_archive_filename(2026, 7, "posts")


def test_missing_torrent_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Torrent directory"):
        find_archive_in_torrents(tmp_path / "missing", 2026, 7, "submissions")


def test_no_torrent_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No .torrent files"):
        find_archive_in_torrents(tmp_path, 2026, 7, "submissions")


def test_download_must_create_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    torrent_dir = tmp_path / "torrents"
    torrent_dir.mkdir()
    (torrent_dir / "monthly.torrent").touch()
    run = Mock(side_effect=[
        subprocess.CompletedProcess(["aria2c"], 0, stdout="4|./RS_2026-01.zst\n"),
        subprocess.CompletedProcess(["aria2c"], 0),
    ])
    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(FileNotFoundError, match="Downloaded archive RS_2026-01.zst"):
        download_reddit_archive(torrent_dir, tmp_path / "raw", 2026, 1)
    assert run.call_count == 2
