"""Small CPU-only tests for new comparison and immutable-output plumbing."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

import evaluate_stationary_flows_v1 as evaluation
import requalify_stationary_flows_v1 as runner


class RequalificationTests(unittest.TestCase):
    def test_normalized_profile_exact_scale(self):
        v = np.zeros((3, 3, 3, 3), dtype=np.float64)
        v[0] = np.arange(27).reshape(3, 3, 3) + 1
        v[1] = .2 * v[0]
        m = evaluation.profile(v, 4 * v, np.ones((3, 3, 3), dtype=bool))
        self.assertEqual(m["normalized_vector_rms_relative"], 0)

    def test_transverse_distortion_detected(self):
        v = np.zeros((3, 2, 2, 2))
        v[0] = 1
        changed = v.copy()
        changed[1, 0, 0, 0] = 1
        m = evaluation.profile(v, changed, np.ones((2, 2, 2), dtype=bool))
        self.assertGreater(m["normalized_vector_rms_relative"], .2)

    def test_nonpositive_flow_rejected(self):
        with self.assertRaises(RuntimeError):
            evaluation.profile(np.zeros((3, 2, 2, 2)), np.zeros((3, 2, 2, 2)), np.ones((2, 2, 2), dtype=bool))

    def test_write_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            runner.write(path, {"value": 1})
            with self.assertRaises(FileExistsError):
                runner.write(path, {"value": 2})
            self.assertEqual(runner.audit.read(path), {"value": 1})

    def test_bad_serialization_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with self.assertRaises(ValueError):
                runner.write(path, {"value": float("nan")})
            self.assertFalse(path.exists())

    def test_tampered_nested_binding_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            runner.write(path, {"value": 1})
            binding = runner.bind(path)
            binding["sha256"] = "0" * 64
            with self.assertRaises(RuntimeError):
                runner.verify_bindings({"cases": [{"source": binding}]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
