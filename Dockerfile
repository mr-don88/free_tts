FROM python:3.10-slim

WORKDIR /app

# Cài ffmpeg + thư viện hệ thống cần cho audio
RUN apt-get update && apt-get install -y ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Tránh lỗi version pip
RUN pip install --upgrade pip setuptools wheel

# Cài thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["python", "app.py"]
