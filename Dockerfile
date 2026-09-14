FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
COPY app.json style-registry.json ./
RUN npm run build
RUN npm prune --omit=dev

FROM node:24-bookworm-slim
ARG APT_MIRROR_HOST=deb.debian.org
RUN sed -i "s|deb.debian.org|${APT_MIRROR_HOST}|g" /etc/apt/sources.list.d/debian.sources \
 && apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 -o Acquire::http::Timeout=30 update \
 && apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 -o Acquire::http::Timeout=30 install -y --no-install-recommends python3 python3-venv libgomp1 libglib2.0-0 libgl1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-ocr.txt ./
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt
ARG INSTALL_OCR=false
RUN if [ "$INSTALL_OCR" = "true" ]; then .venv/bin/pip install --no-cache-dir -r requirements-ocr.txt; fi
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/frontend/dist ./frontend/dist
COPY backend ./backend
COPY renderer ./renderer
COPY scripts/start.py ./scripts/start.py
COPY app.json style-registry.json ./
RUN mkdir -p data /home/node/.paddlex && chown -R node:node /app /home/node/.paddlex
USER node
ENV API_HOST=0.0.0.0
CMD ["python3", "scripts/start.py"]
