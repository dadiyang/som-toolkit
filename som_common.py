"""
som_common: 桌面端和 Android 端共享的工具函数
"""
import os
import sys


def find_omniparser():
    """Search for OmniParser in standard locations."""
    candidates = [
        os.environ.get("OMNIPARSER_DIR", ""),
        os.path.join(os.path.expanduser("~"), "data", "omniparser"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "omniparser"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "OmniParser"),
        os.path.join(os.path.expanduser("~"), "OmniParser"),
    ]
    for path in candidates:
        if path and os.path.isfile(os.path.join(path, "util", "omniparser.py")):
            return path
    sys.exit(
        "ERROR: OmniParser not found.\n"
        "Run install.sh, or set OMNIPARSER_DIR=/path/to/omniparser"
    )


_force_cpu_applied = False

def force_cpu():
    """Force PyTorch to use CPU.

    OmniParser auto-selects MPS on Apple Silicon, but ultralytics/easyocr
    have MPS kernel compatibility issues causing runtime errors.
    Patch torch.backends.mps.is_available to return False before OmniParser init.
    """
    global _force_cpu_applied
    if _force_cpu_applied:
        return
    _force_cpu_applied = True

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    import torch
    if hasattr(torch.backends, "mps") and hasattr(torch.backends.mps, "is_available"):
        torch.backends.mps.is_available = lambda: False


def build_parser_config(use_caption=True):
    """Build OmniParser config dict with weights path resolution."""
    force_cpu()
    omni_dir = find_omniparser()

    default_weights = os.path.join(os.path.expanduser("~"), "data", "models", "omniparser")
    weights_dir = os.environ.get("SOM_WEIGHTS_DIR", default_weights)
    if not os.path.isdir(os.path.join(weights_dir, "icon_detect")):
        legacy = os.path.join(omni_dir, "weights")
        if os.path.isdir(os.path.join(legacy, "icon_detect")):
            weights_dir = legacy

    config = {
        "som_model_path": os.path.join(weights_dir, "icon_detect", "model.pt"),
        "caption_model_name": "florence2",
        "caption_model_path": os.path.join(weights_dir, "icon_caption_florence"),
        "BOX_TRESHOLD": 0.05,
        "use_caption": use_caption,
    }
    return omni_dir, config


def bbox_to_elements(parsed_content, screen_w, screen_h):
    """Convert OmniParser bbox ratios to screen coordinate elements."""
    elements = []
    for idx, item in enumerate(parsed_content):
        bbox = item["bbox"]
        cx = int((bbox[0] + bbox[2]) / 2 * screen_w)
        cy = int((bbox[1] + bbox[3]) / 2 * screen_h)
        w = int((bbox[2] - bbox[0]) * screen_w)
        h = int((bbox[3] - bbox[1]) * screen_h)
        elements.append({
            "index": idx,
            "type": item.get("type", ""),
            "content": item.get("content", ""),
            "interactivity": item.get("interactivity", False),
            "center_x": cx, "center_y": cy,
            "width": w, "height": h,
            "bbox_ratio": bbox,
        })
    return elements


def build_output_json(elements, screen_w, screen_h):
    """Build output JSON with meta information."""
    import time
    return {
        "meta": {
            "screen_w": screen_w,
            "screen_h": screen_h,
            "timestamp": time.time(),
        },
        "elements": elements,
    }


def load_elements(json_path):
    """Load elements from JSON, supporting both old (array) and new (meta+elements) formats."""
    import json
    if not os.path.exists(json_path):
        print(f"ERROR: {json_path} not found. Run som-annotate first.", file=sys.stderr)
        sys.exit(1)
    with open(json_path) as f:
        data = json.load(f)
    if isinstance(data, dict) and "elements" in data:
        return data["elements"], data.get("meta", {})
    return data, {}


def parse_xy(xy_str):
    """Parse x,y coordinate string with validation."""
    parts = xy_str.split(",")
    if len(parts) != 2:
        print(f"ERROR: --xy requires format x,y (e.g. --xy 500,300), got: {xy_str}", file=sys.stderr)
        sys.exit(1)
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        print(f"ERROR: --xy values must be integers, got: {xy_str}", file=sys.stderr)
        sys.exit(1)
