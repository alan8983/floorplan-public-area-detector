"""Basic smoke tests for the pipeline modules."""

import sys
import os
import numpy as np

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing import load_and_binarize, image_stats
from wall_detection import detect_walls, close_wall_gaps
from segmentation import segment_rooms

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "sample1_input_residential_3F.jpg")


def test_load_and_binarize():
    if not os.path.exists(SAMPLE):
        return  # skip if sample not available
    img, gray, binary = load_and_binarize(SAMPLE)
    assert img.ndim == 3
    assert gray.ndim == 2
    assert binary.ndim == 2
    assert binary.dtype == np.uint8


def test_image_stats():
    if not os.path.exists(SAMPLE):
        return
    _, gray, _ = load_and_binarize(SAMPLE)
    stats = image_stats(gray)
    assert "white_ratio" in stats
    assert 0 < stats["white_ratio"] < 1


def test_wall_detection():
    if not os.path.exists(SAMPLE):
        return
    _, _, binary = load_and_binarize(SAMPLE)
    result = detect_walls(binary)
    assert "thick_walls" in result
    assert "walls" in result
    assert "building_bounds" in result
    bt, bb, bl, br = result["building_bounds"]
    assert bt < bb
    assert bl < br


def test_segmentation():
    if not os.path.exists(SAMPLE):
        return
    _, _, binary = load_and_binarize(SAMPLE)
    wall_data = detect_walls(binary)
    walls_closed = close_wall_gaps(wall_data["walls"])
    rooms, labels = segment_rooms(walls_closed, binary)
    assert len(rooms) > 0
    assert labels.shape == binary.shape
    # Each room should have required keys
    for r in rooms:
        assert "label" in r
        assert "area" in r
        assert "bbox" in r
        assert "rel_area" in r


if __name__ == "__main__":
    test_load_and_binarize()
    test_image_stats()
    test_wall_detection()
    test_segmentation()
    print("All tests passed.")
