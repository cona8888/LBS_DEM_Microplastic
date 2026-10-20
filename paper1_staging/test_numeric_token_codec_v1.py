"""Byte fidelity and corruption/resource controls; no numerical integration."""
import json, math, random, struct, unittest
import numeric_token_codec_v1 as codec


class Controls(unittest.TestCase):
    def test_all_float_classes_and_lexical_layout(self):
        rng = random.Random(177)
        values = [0., -0., 1., -1., 5e-324, -5e-324, 1.7976931348623157e308,
                  float('nan'), float('inf'), float('-inf')]
        values.extend(struct.unpack('<d', rng.getrandbits(64).to_bytes(8,'little'))[0] for _ in range(10000))
        obj = dict(values=values, literal='123.45678901234567 \\" \\u0000 µ', integer=10**150)
        for indent in (None, 2, 7):
            raw = json.dumps(obj, indent=indent, ensure_ascii=False, allow_nan=True).encode()
            packed, count = codec.encode(raw)
            self.assertGreater(count, 100)
            self.assertEqual(codec.decode(packed, len(raw)), raw)
            self.assertLessEqual(len(packed), len(raw))

    def test_quoted_numbers_and_noncanonical_spelling_preserved(self):
        raw = b'{"a":1.0000000000000000,"b":"-1.2345678901234567e+11","c": 12.345678901234567}'
        packed, count = codec.encode(raw)
        self.assertEqual(count, 1)
        self.assertEqual(codec.decode(packed, len(raw)), raw)

    def test_corruption_and_expansion_bounds(self):
        raw = b'[1.2345678901234567]'; packed, _ = codec.encode(raw)
        with self.assertRaises(ValueError): codec.decode(packed, len(raw)-1)
        for bad in (b'\x00', b'\x00x', b'\x00d123', b'\x00d'+struct.pack('<d',float('nan')),
                    b'\x00d'+struct.pack('<d',1.)):
            with self.assertRaises(ValueError): codec.decode(bad, 1000)
        with self.assertRaises(ValueError): codec.encode(b'\x00')


if __name__ == '__main__': unittest.main()
