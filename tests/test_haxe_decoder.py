"""
Tests for the Haxe serialization decoder.

These tests verify that the decoder correctly handles all Haxe serialization
format type markers, based on the specification at:
https://haxe.org/manual/std-serialization-format.html
"""

import math
import pytest
from idleon_reader.haxe_decoder import HaxeDecoder, decode_haxe, HaxeDecodeError


class TestPrimitives:
    """Test decoding of primitive Haxe types."""

    def test_null(self):
        assert decode_haxe("n") is None

    def test_true(self):
        assert decode_haxe("t") is True

    def test_false(self):
        assert decode_haxe("f") is False

    def test_zero(self):
        assert decode_haxe("z") == 0

    def test_positive_int(self):
        assert decode_haxe("i456") == 456

    def test_negative_int(self):
        assert decode_haxe("i-123") == -123

    def test_large_int(self):
        assert decode_haxe("i999999") == 999999

    def test_float(self):
        result = decode_haxe("d1.5")
        assert result == 1.5

    def test_float_negative(self):
        result = decode_haxe("d-3.14")
        assert result == pytest.approx(-3.14)

    def test_float_scientific(self):
        result = decode_haxe("d1.45e-8")
        assert result == pytest.approx(1.45e-8)

    def test_nan(self):
        result = decode_haxe("k")
        assert math.isnan(result)

    def test_negative_infinity(self):
        assert decode_haxe("m") == float("-inf")

    def test_positive_infinity(self):
        assert decode_haxe("p") == float("inf")


class TestStrings:
    """Test decoding of Haxe strings."""

    def test_simple_string(self):
        # "y5:hello" -> "hello"
        assert decode_haxe("y5:hello") == "hello"

    def test_empty_string(self):
        assert decode_haxe("y0:") == ""

    def test_url_encoded_string(self):
        # Space encoded as %20. Length is of the URL-encoded form (13 chars)
        assert decode_haxe("y13:hello%20world") == "hello world"

    def test_string_cache_reference(self):
        # String "abc" (cached as index 0), then reference R0
        decoder = HaxeDecoder("y3:abcR0")
        first = decoder._parse()
        assert first == "abc"
        second = decoder._parse()
        assert second == "abc"


class TestArrays:
    """Test decoding of Haxe arrays."""

    def test_empty_array(self):
        assert decode_haxe("ah") == []

    def test_int_array(self):
        # Array of [1, 2, 3]
        assert decode_haxe("ai1i2i3h") == [1, 2, 3]

    def test_mixed_array(self):
        # Array of [1, "hi", true, null]
        result = decode_haxe("ai1y2:hitnh")
        assert result == [1, "hi", True, None]

    def test_array_with_null_run(self):
        # Array with 3 consecutive nulls: [null, null, null, 1]
        result = decode_haxe("au3i1h")
        assert result == [None, None, None, 1]

    def test_nested_array(self):
        # [[1, 2], [3, 4]]
        result = decode_haxe("aai1i2hai3i4hh")
        assert result == [[1, 2], [3, 4]]


class TestMaps:
    """Test decoding of Haxe maps."""

    def test_empty_string_map(self):
        assert decode_haxe("bh") == {}

    def test_string_map(self):
        # {"name": "test", "val": 42}
        # b = StringMap start, y4:name = key "name", y4:test = value "test",
        # y3:val = key "val", i42 = value 42, h = end
        result = decode_haxe("by4:namey4:testy3:vali42h")
        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["val"] == 42

    def test_int_map(self):
        # IntMap {1: "a", 2: "b"}
        result = decode_haxe("q:1y1:a:2y1:bh")
        assert result == {1: "a", 2: "b"}

    def test_empty_int_map(self):
        assert decode_haxe("qh") == {}


class TestObjects:
    """Test decoding of Haxe anonymous objects."""

    def test_empty_object(self):
        assert decode_haxe("og") == {}

    def test_simple_object(self):
        # Object with field "x" = 10
        result = decode_haxe("oy1:xi10g")
        assert result == {"x": 10}


class TestComplexStructures:
    """Test decoding of more complex nested structures."""

    def test_object_with_array(self):
        # Object with a field "items" containing [1, 2]
        result = decode_haxe("oy5:itemsai1i2hg")
        assert result == {"items": [1, 2]}

    def test_string_map_with_nested(self):
        # StringMap with nested objects
        result = decode_haxe("by4:dataoR0i5gh")
        assert isinstance(result, dict)
        assert "data" in result

    def test_deeply_nested(self):
        # Array containing a map containing an array
        result = decode_haxe("aby3:keyai1i2hhh")
        assert isinstance(result, list)
        assert len(result) == 1
        inner = result[0]
        assert isinstance(inner, dict)
        assert inner["key"] == [1, 2]


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_type_marker(self):
        with pytest.raises(HaxeDecodeError):
            decode_haxe("X")

    def test_unexpected_end(self):
        with pytest.raises(HaxeDecodeError):
            decode_haxe("i")  # Integer without digits

    def test_invalid_string_cache_ref(self):
        with pytest.raises(HaxeDecodeError):
            decode_haxe("R99")  # Reference to non-existent cache entry

    def test_empty_input(self):
        result = decode_haxe("")
        assert result is None


class TestIdleOnLikeData:
    """
    Test with data structures that resemble actual IdleOn save data patterns.
    """

    def test_skill_levels_array(self):
        """Skill levels are typically stored as arrays of integers."""
        # [15, 23, 10, 45, 0, 0, 0, 0, 0]
        result = decode_haxe("ai15i23i10i45zzzzzhg"[:-1])  # Remove trailing 'g'
        # Actually let's do this properly
        result = decode_haxe("ai15i23i10i45zzzzzh")
        assert result == [15, 23, 10, 45, 0, 0, 0, 0, 0]

    def test_player_names_array(self):
        """Player names stored as string array."""
        # Array of ["Player", "Warrior", "Mage"]
        result = decode_haxe("ay6:Playery7:Warriory4:Mageh")
        assert isinstance(result, list)
        assert result == ["Player", "Warrior", "Mage"]

    def test_character_class_map(self):
        """Character classes stored as int-keyed map."""
        result = decode_haxe("q:0i4:1i11:2i18h")
        assert result == {0: 4, 1: 11, 2: 18}
        # 4=Warrior, 11=Archer, 18=Mage
