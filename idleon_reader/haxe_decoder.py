"""
Haxe Serialization Format Decoder

Decodes data serialized using Haxe's haxe.Serializer class.
IdleOn (built on Stencyl/Haxe) uses this format to store save data in LevelDB.

Reference: https://haxe.org/manual/std-serialization-format.html
"""

from urllib.parse import unquote
from typing import Any


class HaxeDecodeError(Exception):
    """Raised when the Haxe-serialized data cannot be decoded."""
    pass


class HaxeDecoder:
    """
    Decodes Haxe-serialized binary strings into Python data structures.

    The Haxe serialization format uses single-character type prefixes:
      n = null, t = true, f = false, z = zero,
      i = int, d = float, y = string,
      a = array, l = list,
      o = anonymous object, b = StringMap, q = IntMap, M = ObjectMap,
      R = string cache ref, r = object cache ref,
      k = NaN, m = -Infinity, p = +Infinity
    """

    def __init__(self, data: str):
        self._data = data
        self._pos = 0
        self._string_cache: list[str] = []
        self._object_cache: list[Any] = []
        self._result = None

    def _peek(self) -> str:
        """Look at the current character without advancing."""
        if self._pos >= len(self._data):
            raise HaxeDecodeError(f"Unexpected end of data at position {self._pos}")
        return self._data[self._pos]

    def _read(self) -> str:
        """Read one character and advance position."""
        ch = self._peek()
        self._pos += 1
        return ch

    def _read_until(self, delimiter: str) -> str:
        """Read characters until the delimiter is found, consuming the delimiter."""
        start = self._pos
        idx = self._data.find(delimiter, self._pos)
        if idx == -1:
            raise HaxeDecodeError(
                f"Expected delimiter '{delimiter}' not found from position {self._pos}"
            )
        self._pos = idx + len(delimiter)
        return self._data[start:idx]

    def _read_int(self) -> int:
        """Read an integer value (terminated by next type marker or delimiter)."""
        start = self._pos
        if self._pos < len(self._data) and self._data[self._pos] == '-':
            self._pos += 1
        while self._pos < len(self._data) and self._data[self._pos].isdigit():
            self._pos += 1
        if self._pos == start:
            raise HaxeDecodeError(f"Expected integer at position {start}")
        return int(self._data[start:self._pos])

    def _read_float(self) -> float:
        """Read a float value."""
        start = self._pos
        # Allow negative sign
        if self._pos < len(self._data) and self._data[self._pos] in '-+':
            self._pos += 1
        # Read digits and decimal point
        while self._pos < len(self._data) and self._data[self._pos] in '0123456789.':
            self._pos += 1
        # Read exponent
        if self._pos < len(self._data) and self._data[self._pos] in 'eE':
            self._pos += 1
            if self._pos < len(self._data) and self._data[self._pos] in '-+':
                self._pos += 1
            while self._pos < len(self._data) and self._data[self._pos].isdigit():
                self._pos += 1
        text = self._data[start:self._pos]
        try:
            return float(text)
        except ValueError:
            raise HaxeDecodeError(f"Invalid float '{text}' at position {start}")

    def _read_string(self) -> str:
        """Read a Haxe string: length:url_encoded_content."""
        length = self._read_int()
        if self._read() != ':':
            raise HaxeDecodeError(f"Expected ':' after string length at position {self._pos - 1}")
        raw = self._data[self._pos:self._pos + length]
        self._pos += length
        decoded = unquote(raw)
        self._string_cache.append(decoded)
        return decoded

    def _parse_array(self) -> list:
        """Parse a Haxe array: 'a' items... 'h'."""
        result = []
        self._object_cache.append(result)
        while self._peek() != 'h':
            if self._peek() == 'u':
                # Consecutive null entries
                self._read()  # consume 'u'
                count = self._read_int()
                result.extend([None] * count)
            else:
                result.append(self._parse())
        self._read()  # consume 'h'
        return result

    def _parse_list(self) -> list:
        """Parse a Haxe list: 'l' items... 'h'."""
        result = []
        self._object_cache.append(result)
        while self._peek() != 'h':
            result.append(self._parse())
        self._read()  # consume 'h'
        return result

    def _parse_string_map(self) -> dict:
        """Parse a Haxe StringMap: 'b' (key value)... 'h'."""
        result = {}
        self._object_cache.append(result)
        while self._peek() != 'h':
            key = self._parse()
            value = self._parse()
            result[str(key)] = value
        self._read()  # consume 'h'
        return result

    def _parse_int_map(self) -> dict:
        """Parse a Haxe IntMap: 'q' (:int value)... 'h'."""
        result = {}
        self._object_cache.append(result)
        while self._peek() != 'h':
            if self._read() != ':':
                raise HaxeDecodeError(f"Expected ':' in IntMap key at position {self._pos - 1}")
            key = self._read_int()
            value = self._parse()
            result[key] = value
        self._read()  # consume 'h'
        return result

    def _parse_object_map(self) -> dict:
        """Parse a Haxe ObjectMap: 'M' (key value)... 'h'."""
        result = {}
        self._object_cache.append(result)
        while self._peek() != 'h':
            key = self._parse()
            value = self._parse()
            # Convert key to string for JSON compatibility
            result[str(key)] = value
        self._read()  # consume 'h'
        return result

    def _parse_object(self) -> dict:
        """Parse an anonymous object: 'o' (name value)... 'g'."""
        result = {}
        self._object_cache.append(result)
        while self._peek() != 'g':
            key = self._parse()
            value = self._parse()
            result[str(key)] = value
        self._read()  # consume 'g'
        return result

    def _parse_class_instance(self) -> dict:
        """Parse a class instance: 'c' classname (field value)... 'g'."""
        class_name = self._parse()
        result = {"__class__": class_name}
        self._object_cache.append(result)
        while self._peek() != 'g':
            key = self._parse()
            value = self._parse()
            result[str(key)] = value
        self._read()  # consume 'g'
        return result

    def _parse_enum_by_name(self) -> dict:
        """Parse enum by name: 'w' typename constructor ':' argcount args..."""
        type_name = self._parse()
        constructor = self._parse()
        if self._read() != ':':
            raise HaxeDecodeError(f"Expected ':' in enum at position {self._pos - 1}")
        arg_count = self._read_int()
        args = [self._parse() for _ in range(arg_count)]
        result = {
            "__enum__": type_name,
            "__constructor__": constructor,
            "__args__": args,
        }
        self._object_cache.append(result)
        return result

    def _parse_enum_by_index(self) -> dict:
        """Parse enum by index: 'j' typename ':' index ':' argcount args..."""
        type_name = self._parse()
        if self._read() != ':':
            raise HaxeDecodeError(f"Expected ':' in enum index at position {self._pos - 1}")
        index = self._read_int()
        if self._read() != ':':
            raise HaxeDecodeError(f"Expected ':' after enum index at position {self._pos - 1}")
        arg_count = self._read_int()
        args = [self._parse() for _ in range(arg_count)]
        result = {
            "__enum__": type_name,
            "__index__": index,
            "__args__": args,
        }
        self._object_cache.append(result)
        return result

    def _parse(self) -> Any:
        """Parse the next value from the serialized data."""
        if self._pos >= len(self._data):
            return None

        ch = self._read()

        if ch == 'n':
            return None
        elif ch == 't':
            return True
        elif ch == 'f':
            return False
        elif ch == 'z':
            return 0
        elif ch == 'i':
            return self._read_int()
        elif ch == 'd':
            return self._read_float()
        elif ch == 'k':
            return float('nan')
        elif ch == 'm':
            return float('-inf')
        elif ch == 'p':
            return float('inf')
        elif ch == 'y':
            return self._read_string()
        elif ch == 'R':
            # String cache reference
            idx = self._read_int()
            if idx < 0 or idx >= len(self._string_cache):
                raise HaxeDecodeError(
                    f"String cache reference {idx} out of range (cache size: {len(self._string_cache)})"
                )
            return self._string_cache[idx]
        elif ch == 'r':
            # Object cache reference
            idx = self._read_int()
            if idx < 0 or idx >= len(self._object_cache):
                raise HaxeDecodeError(
                    f"Object cache reference {idx} out of range (cache size: {len(self._object_cache)})"
                )
            return self._object_cache[idx]
        elif ch == 'a':
            return self._parse_array()
        elif ch == 'l':
            return self._parse_list()
        elif ch == 'o':
            return self._parse_object()
        elif ch == 'b':
            return self._parse_string_map()
        elif ch == 'q':
            return self._parse_int_map()
        elif ch == 'M':
            return self._parse_object_map()
        elif ch == 'c':
            return self._parse_class_instance()
        elif ch == 'w':
            return self._parse_enum_by_name()
        elif ch == 'j':
            return self._parse_enum_by_index()
        elif ch == 's':
            # Base64-encoded bytes
            length = self._read_int()
            if self._read() != ':':
                raise HaxeDecodeError(f"Expected ':' after bytes length at position {self._pos - 1}")
            raw = self._data[self._pos:self._pos + length]
            self._pos += length
            return f"<bytes:{raw}>"
        elif ch == 'v':
            # Date
            date_str = self._read_until(':')  # There's no standard delimiter; read until next marker
            return f"<date:{date_str}>"
        elif ch == 'x':
            # Exception wrapper
            return {"__exception__": self._parse()}
        else:
            raise HaxeDecodeError(f"Unknown type marker '{ch}' at position {self._pos - 1}")

    @property
    def result(self) -> Any:
        """Decode the data and return the result."""
        if self._result is None:
            self._pos = 0
            self._string_cache.clear()
            self._object_cache.clear()
            self._result = self._parse()
        return self._result


def decode_haxe(data: str) -> Any:
    """
    Convenience function to decode a Haxe-serialized string.

    Args:
        data: The Haxe-serialized string to decode.

    Returns:
        The decoded Python data structure (dict, list, str, int, float, etc.)
    """
    return HaxeDecoder(data).result


def try_decode_value(value: str) -> Any:
    """
    Try to decode a value as Haxe serialization. If it fails,
    try JSON, then return the raw string.
    """
    import json

    if not value or not isinstance(value, str):
        return value

    # Try Haxe decode
    try:
        return decode_haxe(value)
    except (HaxeDecodeError, IndexError, RecursionError):
        pass

    # Try JSON
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        pass

    # Return raw string
    return value
