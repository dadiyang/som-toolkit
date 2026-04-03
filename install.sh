#!/bin/bash
# SoM Toolkit 安装脚本
# 跨平台：Linux / macOS (Intel & Apple Silicon)
set -e
# Note: This script is for macOS/Linux. Windows users: pip install the dependencies manually.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== SoM Toolkit Installer ==="
echo "Install dir: $SCRIPT_DIR"

# 1. Python 环境检查
PYTHON=${PYTHON:-python3}
if ! command -v $PYTHON &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    exit 1
fi
echo "Python: $($PYTHON --version)"

# 2. 创建 venv (gitignore 已排除)
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtualenv..."
    $PYTHON -m venv "$SCRIPT_DIR/venv"
fi
source "$SCRIPT_DIR/venv/bin/activate"

# 3. 安装 PyTorch (根据平台选择)
echo "Installing PyTorch..."
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS - CPU only (MPS has kernel compatibility issues with OmniParser)
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
elif command -v nvidia-smi &>/dev/null; then
    # Linux with NVIDIA GPU
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
else
    # Linux CPU only
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
fi

# 4. 安装 OmniParser 依赖
echo "Installing OmniParser dependencies..."
pip install \
    ultralytics==8.3.70 \
    easyocr \
    supervision==0.18.0 \
    "transformers==4.46.3" \
    accelerate \
    timm \
    einops==0.8.0 \
    Pillow \
    opencv-python-headless

# 5. 安装平台操控工具（统一用 pyautogui，三平台通用）
echo "Installing UI automation tools..."
pip install pyautogui pyperclip

if [[ "$(uname)" == "Linux" ]]; then
    # pyautogui on Linux needs xdotool and scrot as backends
    if ! command -v xdotool &>/dev/null; then
        echo "WARN: xdotool not found. Install with: sudo apt install xdotool"
    fi
    if ! command -v scrot &>/dev/null; then
        echo "WARN: scrot not found. Install with: sudo apt install scrot"
    fi
fi

# 6. 下载 OmniParser 源码到 ~/data/omniparser/ (不污染项目目录)
OMNI_DIR="${OMNIPARSER_DIR:-$HOME/data/omniparser}"
echo "Setting up OmniParser at $OMNI_DIR ..."
mkdir -p "$OMNI_DIR/util"

# Download from GitHub as zip if not exists
if [ ! -f "$OMNI_DIR/util/omniparser.py" ]; then
    echo "Downloading OmniParser source..."
    TMP_ZIP="/tmp/omniparser_src.zip"
    curl -L --connect-timeout 30 --max-time 300 \
         -o "$TMP_ZIP" \
         "https://github.com/microsoft/OmniParser/archive/refs/heads/master.zip"
    unzip -q -o "$TMP_ZIP" "OmniParser-master/util/*" -d /tmp/
    cp -r /tmp/OmniParser-master/util/* "$OMNI_DIR/util/"
    rm -rf "$TMP_ZIP" /tmp/OmniParser-master
fi

echo "OmniParser source: $OMNI_DIR"
echo "To use a different location: export OMNIPARSER_DIR=/your/path"

# 7. Patch utils.py for compatibility (use Python for cross-platform reliability)
echo "Patching for compatibility..."
UTILS="$OMNI_DIR/util/utils.py"
if [ -f "$UTILS" ]; then
    $PYTHON -c "
import pathlib
p = pathlib.Path('$UTILS')
text = p.read_text()
changed = False
if 'from openai import AzureOpenAI' in text and 'try:' not in text.split('from openai import AzureOpenAI')[0][-20:]:
    text = text.replace(
        'from openai import AzureOpenAI',
        'try:\n    from openai import AzureOpenAI\nexcept ImportError:\n    AzureOpenAI = None'
    )
    changed = True
if \"reader = easyocr.Reader(['en'])\" in text:
    text = text.replace(
        \"reader = easyocr.Reader(['en'])\",
        \"reader = easyocr.Reader(['en'], gpu=False)\"
    )
    changed = True
if changed:
    p.write_text(text)
    print('Patched utils.py')
else:
    print('utils.py already patched or no changes needed')
"
fi

# 8. 下载模型权重到 ~/data/models/omniparser/ (不污染源码)
WEIGHTS_DIR="${SOM_WEIGHTS_DIR:-$HOME/data/models/omniparser}"
echo "Downloading model weights to $WEIGHTS_DIR ..."
mkdir -p "$WEIGHTS_DIR/icon_detect" "$WEIGHTS_DIR/icon_caption_florence"

# Set HF mirror for China
export HF_ENDPOINT=${HF_ENDPOINT:-https://hf-mirror.com}

pip install huggingface_hub

python3 -c "
import os
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
from huggingface_hub import hf_hub_download

weights_dir = '$WEIGHTS_DIR'

# Icon detection model (~39MB)
for f in ['model.pt', 'model.yaml', 'train_args.yaml']:
    print(f'Downloading icon_detect/{f}...')
    hf_hub_download('microsoft/OmniParser-v2.0', f'icon_detect/{f}', local_dir=weights_dir)

# Icon caption model (~1GB, optional for --no-caption mode)
for f in ['config.json', 'generation_config.json', 'model.safetensors']:
    dst = os.path.join(weights_dir, 'icon_caption_florence', f)
    if not os.path.exists(dst):
        print(f'Downloading icon_caption/{f}...')
        path = hf_hub_download('microsoft/OmniParser-v2.0', f'icon_caption/{f}', local_dir=weights_dir)
        src = os.path.join(weights_dir, 'icon_caption', f)
        if os.path.exists(src) and not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)
print('Model weights ready!')
"

echo ""
echo "Weights: $WEIGHTS_DIR"
echo "Source:  $OMNI_DIR"
echo "To override: SOM_WEIGHTS_DIR, OMNIPARSER_DIR"

echo ""
echo "=== Installation Complete ==="
echo "Usage (Desktop):"
echo "  source $SCRIPT_DIR/venv/bin/activate"
echo "  python3 som-toolkit/som-annotate --no-caption -o page.jpg -j page.json"
echo "  python3 som-toolkit/som-find --summary -j page.json"
echo "  python3 som-toolkit/som-click 42 -j page.json"
echo ""
echo "For Android tools, also install:"
echo "  - ADB (Android Debug Bridge): sudo apt install adb"
echo "  - ADB Keyboard on the Android device"
