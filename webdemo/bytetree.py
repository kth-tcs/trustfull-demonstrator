#!/usr/bin/env python
from collections.abc import Sequence
from typing import ByteString, Iterator, List, Tuple, Union

BYTEORDER = "big"

ByteTreeValue = Union[ByteString, Sequence["ByteTree"]]


class ByteTree:
    """
    Class representing a byte tree, as defined by Verificatum.

    For the exact spec, see Appendix A of the "User Manual for the Verificatum Mix-Net".
    https://www.verificatum.org/files/vmnum-3.0.4.pdf
    """

    NODE = 0
    LEAF = 1

    def __init__(self, value: ByteTreeValue) -> None:
        if not isinstance(value, Sequence):
            raise TypeError("value should be of type Sequence")

        self.type: int
        if isinstance(value[0], int):
            self.type = ByteTree.LEAF
        else:
            self.type = ByteTree.NODE
        self.value: ByteTreeValue = value

    def is_node(self) -> bool:
        return self.type == ByteTree.NODE

    def is_leaf(self) -> bool:
        return self.type == ByteTree.LEAF

    @classmethod
    def from_byte_array(cls, source: ByteString) -> "ByteTree":
        """
        Read a byte tree from a byte array
        """
        return cls._from_byte_array(source, 0)[0]

    @classmethod
    def _from_byte_array(cls, source: ByteString, index=0) -> Tuple["ByteTree", int]:
        original_index = index
        tpe = source[index]
        assert tpe in (cls.NODE, cls.LEAF)

        index += 1
        length = int.from_bytes(bytes(source[index : index + 4]), BYTEORDER)
        assert length >= 0

        index += 4
        if tpe == cls.LEAF:
            if index + length > len(source):
                raise ValueError("Length larger than source")
            byte_tree = cls(source[index : index + length])
            index += length
        else:
            children = []
            for _ in range(length):
                child, offset = cls._from_byte_array(source, index)
                children.append(child)
                index += offset
            byte_tree = cls(children)
        return byte_tree, index - original_index

    def to_byte_array(self) -> ByteString:
        """
        Convert byte tree to its continuous byte array representation.
        """
        byte_array = self.type.to_bytes(1, BYTEORDER)
        byte_array += len(self.value).to_bytes(4, BYTEORDER)
        # index = 0 + 1 + 4

        if self.is_leaf():
            byte_array += bytes(self.value)
            # index += len(self.value)
        else:
            for child in self.value:
                child: "ByteTree"

                byte_array += child.to_byte_array()
                # index += offset

        return byte_array

    def pretty_str(self, indent: int = 0) -> str:
        """
        Writes formatted string illustrating the byte tree.

        See `ByteTreeBasic::prettyWriteTo` in verificatum-vcr.
        """
        return "".join(self._pretty_str(indent))

    def _pretty_str(self, indent: int) -> Iterator[str]:
        s = 2 * indent * " "
        if self.is_leaf():
            data = "".join(_byte_to_hex(x) for x in self.value)
            yield f'{s}"{data}"'
        else:
            yield f"{s}[\n"
            for idx, child in enumerate(self.value):
                child: "ByteTree"

                is_last = idx == len(self.value) - 1

                yield from child.pretty_str(indent + 1)
                if not is_last:
                    yield ","
                yield "\n"
            yield f"{s}]"


def _byte_to_hex(x: int) -> str:
    x = hex(x)[2:]
    assert len(x) in (1, 2)
    return x.rjust(2, "0")


def _main(args: List[str]) -> int:
    """
    Port of `vbt`'s base functionality in python.
    """
    if len(args) > 2:
        print("Usage:", args[0], "<filename>", file=sys.stderr)
        return 1
    elif len(args) == 2:
        with open(args[1], "rb") as f:
            inp = f.read()
    else:
        inp = sys.stdin.read()

    print(byte_array_byte_tree_to_json(bytearray(inp)))
    return 0


def byte_array_byte_tree_to_json(ba: ByteString):
    return ByteTree.from_byte_array(ba).pretty_str()


if __name__ == "__main__":
    import sys

    sys.exit(_main(sys.argv))
