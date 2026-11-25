"""Xử lý kéo-thả đường dẫn, chuyển Thùng rác hệ thống và xóa vĩnh viễn cho Living Recycle Bin."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from urllib.parse import quote, unquote

from PySide6.QtCore import QFile, QUrl


def has_droppable_data(md) -> bool:
    if md is None:
        return False
    return (
        md.hasUrls()
        or md.hasFormat("text/uri-list")
        or md.hasFormat("x-special/gnome-copied-files")
        or md.hasText()
    )


def parse_uri_to_local_path(raw: str) -> str | None:
    s = raw.strip().strip("\x00")
    if not s or s.startswith("#"):
        return None
    if s.lower().startswith("file://"):
        url = QUrl(s)
        path = url.toLocalFile()
        if not path:
            path = unquote(s[7:])
        return path or None
    if os.path.isabs(s) and os.path.lexists(s):
        return s
    return None


def extract_dropped_paths(md) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()

    def add_path(p: str | None) -> None:
        if p and os.path.lexists(p):
            norm = os.path.abspath(p)
            if norm not in seen:
                seen.add(norm)
                paths.append(norm)

    if md.hasUrls():
        for url in md.urls():
            if url.isLocalFile():
                add_path(url.toLocalFile())
            else:
                add_path(parse_uri_to_local_path(url.toString()))

    for fmt in ("text/uri-list", "x-special/gnome-copied-files"):
        if md.hasFormat(fmt):
            raw_bytes = bytes(md.data(fmt))
            text = raw_bytes.decode("utf-8", errors="ignore")
            lines = text.splitlines()
            if fmt == "x-special/gnome-copied-files" and lines and lines[0].strip() in ("copy", "cut"):
                lines = lines[1:]
            for line in lines:
                add_path(parse_uri_to_local_path(line))

    if not paths and md.hasText():
        for line in md.text().splitlines():
            add_path(parse_uri_to_local_path(line))

    return paths


def permanently_delete_path(path: str) -> bool:
    try:
        if os.path.islink(path) or os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        return not os.path.lexists(path)
    except Exception:
        return False


def move_path_to_trash(path: str) -> bool:
    try:
        if QFile.moveToTrash(path) and not os.path.lexists(path):
            return True
    except Exception:
        pass
    if sys.platform.startswith("linux") and shutil.which("gio"):
        try:
            res = subprocess.run(
                ["gio", "trash", path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode == 0 and not os.path.lexists(path):
                return True
        except Exception:
            pass
    if sys.platform.startswith("linux"):
        try:
            trash_root = os.path.expanduser("~/.local/share/Trash")
            files_dir = os.path.join(trash_root, "files")
            info_dir = os.path.join(trash_root, "info")
            os.makedirs(files_dir, exist_ok=True)
            os.makedirs(info_dir, exist_ok=True)

            base = os.path.basename(path.rstrip(os.sep)) or "item"
            dest_name = base
            idx = 1
            while os.path.lexists(os.path.join(files_dir, dest_name)):
                stem, ext = os.path.splitext(base)
                dest_name = f"{stem}_{idx}{ext}"
                idx += 1

            dest_path = os.path.join(files_dir, dest_name)
            info_path = os.path.join(info_dir, f"{dest_name}.trashinfo")
            del_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            with open(info_path, "w", encoding="utf-8") as f:
                f.write("[Trash Info]\n")
                f.write(f"Path={quote(os.path.abspath(path), safe='/')}\n")
                f.write(f"DeletionDate={del_date}\n")
            shutil.move(path, dest_path)
            return not os.path.lexists(path)
        except Exception:
            pass
    return False
