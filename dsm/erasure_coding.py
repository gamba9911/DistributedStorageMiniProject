# dsm/erasure_coding.py

import math
from dataclasses import dataclass
from typing import List, Dict, Any

import pyerasure
import pyerasure.finite_field
import pyerasure.generator


@dataclass
class CodedFragment:
    """
    One erasure-coded fragment.

    type = "systematic"  -> original symbol, we know its index
         = "coded"       -> RLNC-coded symbol, we store coefficients
    """
    frag_id: int          # 0 .. (c + l - 1), just an index for storage
    data: bytes           # symbol bytes
    kind: str             # "systematic" or "coded"
    symbol_index: int | None  # index for systematic symbols
    coeffs: bytes | None      # coefficients for coded symbols


@dataclass
class ErasureMeta:
    """
    Metadata needed to decode a file.
    """
    c: int                 # number of source symbols
    l: int                 # tolerated losses
    symbol_bytes: int      # bytes per symbol
    data_len: int          # original file length in bytes


class ErasureCoder:
    """
    Small wrapper around PyErasure using RLNC.

    For a file of B bytes:
      - choose c and l
      - produce (c + l) coded fragments
      - can reconstruct from any c linearly independent fragments
    """

    def __init__(self, c: int, l: int):
        if c <= 0:
            raise ValueError("c must be > 0")
        if l < 0:
            raise ValueError("l must be >= 0")
        self.c = c
        self.l = l
        self.field = pyerasure.finite_field.Binary8()

    def _make_encoder(self, symbol_bytes: int):
        import pyerasure  # local import just in case
        encoder = pyerasure.Encoder(self.field, self.c, symbol_bytes)
        return encoder

    def _make_decoder(self, symbol_bytes: int):
        import pyerasure
        decoder = pyerasure.Decoder(self.field, self.c, symbol_bytes)
        return decoder

    # --------------- ENCODE ---------------

    def encode(self, data: bytes) -> tuple[ErasureMeta, List[CodedFragment]]:
        """
        Encode input data into c+l coded fragments.
        """
        B = len(data)
        # size of each symbol
        symbol_bytes = math.ceil(B / self.c)

        encoder = self._make_encoder(symbol_bytes)
        generator = pyerasure.generator.RandomUniform(self.field, encoder.symbols)

        # Pad data to encoder.block_bytes
        buf = bytearray(encoder.block_bytes)
        buf[:B] = data
        encoder.set_symbols(buf)

        fragments: List[CodedFragment] = []

        # First: systematic symbols (original c fragments)
        for idx in range(self.c):
            sym = bytes(encoder.symbol_data(idx))
            fragments.append(
                CodedFragment(
                    frag_id=len(fragments),
                    data=sym,
                    kind="systematic",
                    symbol_index=idx,
                    coeffs=None,
                )
            )

        # Then: l coded symbols (random linear combinations)
        for _ in range(self.l):
            coeffs = generator.generate()
            sym = encoder.encode_symbol(coeffs)
            fragments.append(
                CodedFragment(
                    frag_id=len(fragments),
                    data=bytes(sym),
                    kind="coded",
                    symbol_index=None,
                    coeffs=bytes(coeffs),
                )
            )

        meta = ErasureMeta(
            c=self.c,
            l=self.l,
            symbol_bytes=symbol_bytes,
            data_len=B,
        )
        return meta, fragments

    # --------------- DECODE ---------------

    def decode(self, meta: ErasureMeta, fragments: List[CodedFragment]) -> bytes:
        """
        Decode from any subset of coded fragments.
        Needs at least c linearly independent symbols.
        """
        if len(fragments) < meta.c:
            raise ValueError("Not enough fragments to decode")

        decoder = self._make_decoder(meta.symbol_bytes)

        # Feed fragments in any order until decoder is complete.
        for frag in fragments:
            if decoder.is_complete():
                break

            if frag.kind == "systematic":
                if frag.symbol_index is None:
                    raise ValueError("systematic fragment missing symbol_index")
                decoder.decode_systematic_symbol(
                    bytearray(frag.data),
                    frag.symbol_index,
                )
            else:
                if frag.coeffs is None:
                    raise ValueError("coded fragment missing coeffs")
                decoder.decode_symbol(
                    bytearray(frag.data),
                    bytearray(frag.coeffs),
                )

        if not decoder.is_complete():
            raise RuntimeError("Decoder did not complete - not enough independent fragments")

        full_block = decoder.block_data()
        # Trim to original length
        return bytes(full_block[:meta.data_len])
