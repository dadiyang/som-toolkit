#!/bin/bash
# SoM Toolkit 安装脚本
# 跨平台：Linux / macOS (Intel & Apple Silicon)
set -e

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

# 2. 创建 venv (避免污染系统环境)
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtualenv..."
    $PYTHON -m venv "$SCRIPT_DIR/venv"
fi
source "$SCRIPT_DIR/venv/bin/activate"

# 3. 安装 PyTorch (根据平台选择)
echo "Installing PyTorch..."
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS - MPS backend
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

# 5. 安装平台特定的操控工具
echo "Installing platform tools..."
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS: pyobjc for CGEvent mouse control + Accessibility API
    pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
    # cliclick is the most reliable macOS mouse control tool
    if ! command -v cliclick &>/dev/null; then
        if command -v brew &>/dev/null; then
            echo "Installing cliclick via Homebrew..."
            brew install cliclick
        else
            echo "WARN: cliclick not found. Install Homebrew first, then: brew install cliclick"
            echo "       Falling back to pyobjc CGEvent (also works but slower)"
        fi
    fi
    # xclip equivalent for macOS is pbcopy/pbpaste (built-in)
    echo "macOS: Using cliclick/CGEvent for clicking, pbcopy/pbpaste for clipboard"
else
    # Linux: xdotool + scrot
    if ! command -v xdotool &>/dev/null; then
        echo "WARN: xdotool not found. Install with: sudo apt install xdotool"
    fi
    if ! command -v scrot &>/dev/null; then
        echo "WARN: scrot not found. Install with: sudo apt install scrot"
    fi
fi

# 6. 下载 OmniParser 源码 (只需要 util/ 目录)
echo "Setting up OmniParser..."
OMNI_DIR="$SCRIPT_DIR/omniparser"
mkdir -p "$OMNI_DIR/util"

# Download from GitHub as zip if not exists
if [ ! -f "$OMNI_DIR/util/omniparser.py" ]; then
    echo "Downloading OmniParser source..."
    TMP_ZIP="/tmp/omniparser_src.zip"
    curl -L -o "$TMP_ZIP" "https://github.com/microsoft/OmniParser/archive/refs/heads/master.zip" 2>/dev/null
    unzip -q -o "$TMP_ZIP" "OmniParser-master/util/*" -d /tmp/
    cp -r /tmp/OmniParser-master/util/* "$OMNI_DIR/util/"
    rm -rf "$TMP_ZIP" /tmp/OmniParser-master
fi

# 7. Patch utils.py for compatibility
echo "Patching for compatibility..."
UTILS="$OMNI_DIR/util/utils.py"
if [ -f "$UTILS" ]; then
    # Fix PaddleOCR compatibility
    sed -i.bak 's/from openai import AzureOpenAI/try:\n    from openai import AzureOpenAI\nexcept ImportError:\n    AzureOpenAI = None/' "$UTILS" 2>/dev/null || true
    # Fix easyocr to use CPU
    sed -i.bak "s/reader = easyocr.Reader(\['en'\])/reader = easyocr.Reader(['en'], gpu=False)/" "$UTILS" 2>/dev/null || true
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
echo "Weights location: $WEIGHTS_DIR"
echo "To use a different location: export SOM_WEIGHTS_DIR=/your/path"

echo ""
echo "=== Installation Complete ==="
echo "Usage:"
echo "  source $SCRIPT_DIR/venv/bin/activate"
echo "  som-annotate                    # Annotate current screen"
echo "  som-click <element_number>      # Click element by SoM number"
echo "  som-type <element_number> text  # Click element and type text"
