#!/bin/bash
# Vibe Investment 启动脚本

echo "🚀 Starting Vibe Investment System..."

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.10+"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# 检查.env
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your API keys!"
    exit 1
fi

# 启动应用
echo "✨ Starting Chainlit server..."
echo "🌐 Open http://localhost:8000 in your browser"
echo ""

chainlit run app.py -w
