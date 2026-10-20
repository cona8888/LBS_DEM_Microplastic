#!/usr/bin/env python3
"""Pure geometry helpers for Stage28a two-fibre periodic placement."""

from __future__ import annotations

from itertools import product

import numpy as np


def segment_segment_distance(a0, a1, b0, b1) -> float:
    """Return the Euclidean distance between two closed 3-D line segments."""
    p0 = np.asarray(a0, dtype=float)
    p1 = np.asarray(a1, dtype=float)
    q0 = np.asarray(b0, dtype=float)
    q1 = np.asarray(b1, dtype=float)
    u = p1 - p0
    v = q1 - q0
    w = p0 - q0
    a = float(np.dot(u, u))
    b = float(np.dot(u, v))
    c = float(np.dot(v, v))
    d = float(np.dot(u, w))
    e = float(np.dot(v, w))
    denominator = a * c - b * b
    small = 1.0e-30
    s_num, s_den = denominator, denominator
    t_num, t_den = denominator, denominator
    if denominator < small:
        s_num, s_den = 0.0, 1.0
        t_num, t_den = e, c
    else:
        s_num = b * e - c * d
        t_num = a * e - b * d
        if s_num < 0.0:
            s_num = 0.0
            t_num, t_den = e, c
        elif s_num > s_den:
            s_num = s_den
            t_num, t_den = e + b, c
    if t_num < 0.0:
        t_num = 0.0
        if -d < 0.0:
            s_num = 0.0
        elif -d > a:
            s_num = s_den
        else:
            s_num, s_den = -d, a
    elif t_num > t_den:
        t_num = t_den
        if -d + b < 0.0:
            s_num = 0.0
        elif -d + b > a:
            s_num = s_den
        else:
            s_num, s_den = -d + b, a
    sc = 0.0 if abs(s_num) < small else s_num / s_den
    tc = 0.0 if abs(t_num) < small else t_num / t_den
    delta = w + sc * u - tc * v
    return float(np.linalg.norm(delta))


def periodic_segment_distance(a0, a1, b0, b1, cell_lengths) -> float:
    """Minimum segment distance over the 27 nearest orthogonal images."""
    lengths = np.asarray(cell_lengths, dtype=float)
    q0 = np.asarray(b0, dtype=float)
    q1 = np.asarray(b1, dtype=float)
    return min(
        segment_segment_distance(
            a0,
            a1,
            q0 + np.asarray(shift, dtype=float) * lengths,
            q1 + np.asarray(shift, dtype=float) * lengths,
        )
        for shift in product((-1, 0, 1), repeat=3)
    )


def translated_segment(fibre: dict, translation_m: float):
    direction = np.asarray(fibre["pull_direction"], dtype=float)
    rear = np.asarray(fibre["rear_m"], dtype=float) + direction * float(translation_m)
    tip = np.asarray(fibre["tip_m"], dtype=float) + direction * float(translation_m)
    return rear, tip


def synchronous_distance_history(first: dict, second: dict, cell_lengths, translations):
    values = []
    for translation in np.asarray(translations, dtype=float):
        a0, a1 = translated_segment(first, float(translation))
        b0, b1 = translated_segment(second, float(translation))
        values.append(periodic_segment_distance(a0, a1, b0, b1, cell_lengths))
    return np.asarray(values, dtype=float)


def candidate_to_fibre(candidate: dict, fibre_id: str) -> dict:
    return {
        "fibre_id": fibre_id,
        "rear_m": [float(value) for value in candidate["rear_m"]],
        "tip_m": [float(value) for value in candidate["tip_m"]],
        "pull_direction": [float(value) for value in candidate["pull_direction"]],
        "source_face_index": int(candidate["face_index"]),
        "source_orientation_sign": float(candidate["orientation_sign"]),
        "source_first_contact_translation_m": candidate["first_sampled_contact_translation_m"],
        "source_minimum_swept_clearance_m": float(candidate["minimum_sampled_swept_clearance_m"]),
    }

