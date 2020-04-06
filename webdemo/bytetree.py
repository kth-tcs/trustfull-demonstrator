from collections.abc import Sequence

BYTEORDER = "big"


class ByteTree:
    NODE = 0
    LEAF = 1

    def __init__(self, value):
        if not isinstance(value, Sequence):
            raise TypeError("value should be of type Sequence")

        if isinstance(value[0], int):
            self.type = ByteTree.LEAF
        else:
            self.type = ByteTree.NODE
        self.value = value

    def is_node(self):
        return self.type == ByteTree.NODE

    def is_leaf(self):
        return self.type == ByteTree.LEAF

    @classmethod
    def from_byte_array(cls, source):
        return cls._from_byte_array(source, 0)[0]

    @classmethod
    def _from_byte_array(cls, source, index=0):
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
            bt = cls(source[index : index + length])
            index += length
        else:
            children = []
            for _ in range(length):
                child, offset = cls._from_byte_array(source, index)
                children.append(child)
                index += offset
            bt = cls(children)
        return bt, index - original_index

    def to_byte_array(self):
        dest = self.type.to_bytes(1, BYTEORDER)
        dest += len(self.value).to_bytes(4, BYTEORDER)
        # index = 0 + 1 + 4

        if self.is_leaf():
            dest += bytes(self.value)
            # index += len(self.value)
        else:
            for child in self.value:
                # child_bytes, offset = child.to_byte_array()
                dest += child.to_byte_array()
                # index += offset

        return dest
