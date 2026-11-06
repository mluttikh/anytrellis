"""Binary encodings for arrays sent to the browser.

Arrays travel as raw little-endian typed buffers described by a small JSON descriptor, so
the browser can view them without parsing or copying. The descriptor's ``id`` is a hash of
the bytes and the dtype: identical data always has the same id and is sent once.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np

DTYPES = {
    "float64": "<f8",
    "float32": "<f4",
    "int32": "<i4",
    "uint32": "<u4",
    "uint16": "<u2",
    "uint8": "u1",
}
"""The dtypes the browser reads, and their NumPy spelling."""


@dataclass(frozen=True)
class Encoded:
    """An encoded array: a JSON-able descriptor plus the raw bytes."""

    descriptor: dict[str, Any]
    data: bytes

    @property
    def id(self) -> str:
        return self.descriptor["id"]


def encode(values: Any, dtype: str, *, components: int = 1) -> Encoded:
    """Encode an array of shape ``(n,)`` or ``(n, components)`` as ``dtype``."""
    if dtype not in DTYPES:
        raise ValueError(f"unknown dtype {dtype!r}; known: {list(DTYPES)}")
    arr = np.asarray(values)
    if arr.ndim == 2 and arr.shape[1] != components:
        raise ValueError(f"expected {components} components, got shape {arr.shape}")
    if arr.ndim == 1 and components > 1:
        raise ValueError("pass a (n, components) array for interleaved data")
    data = np.ascontiguousarray(arr.astype(DTYPES[dtype], copy=False)).tobytes()
    count = int(arr.shape[0]) if arr.ndim else 1
    digest = hashlib.blake2b(data, digest_size=12).hexdigest()
    descriptor = {
        "id": f"{digest}-{dtype}-{components}",
        "dtype": dtype,
        "count": count,
        "components": components,
        "byteLength": len(data),
    }
    return Encoded(descriptor, data)


class Buffers:
    """The buffers of a plot's spec, by id: what the browser may ask for."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def add(self, values: Any, dtype: str, *, components: int = 1) -> dict[str, Any]:
        """Encode ``values``, keep the bytes, and return the descriptor for the spec."""
        enc = encode(values, dtype, components=components)
        self.data[enc.id] = enc.data
        return enc.descriptor
