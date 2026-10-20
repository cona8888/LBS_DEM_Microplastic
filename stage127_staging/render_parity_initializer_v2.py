"""Versioned Stage127 renderer after the local Tk backend failure."""
import render_parity_initializer_v1 as v1

v1.OUTPUT = v1.job.EVAL / "render_02"

if __name__ == "__main__":
    v1.main()
