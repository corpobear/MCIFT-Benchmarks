from __future__ import annotations

import io
import json
import shutil
import subprocess
import zipfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import numpy.typing as npt

from mcift_benchmarks.storage import blob_client

IMS_DATASET_ID = "nasa-ims-bearing"
EXPECTED_PREFIX = "datasets/ims/"


class BlobRangeReader(io.RawIOBase):
    """Seekable range reader used to open the staged outer ZIP without downloading it."""

    def __init__(self, uri: str) -> None:
        self.client = blob_client(uri)
        self.size = self.client.get_blob_properties().size
        self.position = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.position = offset
        elif whence == 1:
            self.position += offset
        elif whence == 2:
            self.position = self.size + offset
        else:
            raise ValueError("invalid seek origin")
        if self.position < 0:
            raise ValueError("negative seek")
        return self.position

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self.size - self.position
        size = min(size, self.size - self.position)
        if size <= 0:
            return b""
        data = self.client.download_blob(offset=self.position, length=size).readall()
        self.position += len(data)
        return bytes(data)


def source_uri_from_manifest(manifest_uri: str) -> tuple[str, str]:
    manifest_bytes = blob_client(manifest_uri).download_blob().readall()
    manifest_hash = __import__("hashlib").sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    files = manifest.get("files", [])
    if len(files) != 1 or files[0].get("path") != "source/IMS.zip":
        raise ValueError("IMS manifest must identify exactly source/IMS.zip")
    return manifest_uri.rsplit("/", 2)[0] + "/source/IMS.zip", manifest_hash


def extract_set2(manifest_uri: str, work_dir: Path) -> tuple[Path, str]:
    source_uri, manifest_hash = source_uri_from_manifest(manifest_uri)
    rar_path = work_dir / "2nd_test.rar"
    with zipfile.ZipFile(BlobRangeReader(source_uri)) as outer:
        with outer.open("IMS/2nd_test.rar") as source, rar_path.open("wb") as destination:
            shutil.copyfileobj(source, destination, 1024 * 1024)
    output_dir = work_dir / "set2"
    output_dir.mkdir()
    extractor = shutil.which("bsdtar") or shutil.which("tar")
    if extractor is None:
        raise RuntimeError("libarchive bsdtar/tar is required to extract IMS Set 2")
    subprocess.run(
        [extractor, "-xf", str(rar_path), "-C", str(output_dir)],
        check=True,
        capture_output=True,
    )
    rar_path.unlink()
    return output_dir, manifest_hash


def recording_paths(extracted: Path) -> list[Path]:
    paths = sorted(path for path in extracted.rglob("*") if path.is_file())
    if len(paths) != 984:
        raise ValueError(f"expected 984 IMS Set 2 recordings, found {len(paths)}")
    return paths


def load_recording(path: Path) -> npt.NDArray[np.float64]:
    values = np.loadtxt(path, delimiter="\t", dtype=np.float64)
    if values.shape != (20480, 4):
        raise ValueError(f"unexpected IMS recording shape for {path.name}: {values.shape}")
    return np.asarray(values, dtype=np.float64)


def iter_recordings(paths: list[Path]) -> Iterator[tuple[str, npt.NDArray[np.float64]]]:
    for path in paths:
        yield path.name, load_recording(path)
