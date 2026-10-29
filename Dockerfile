FROM node:24.18.0-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS compiler
RUN apt-get update && apt-get install -y --no-install-recommends gcc make libgmp-dev curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp
RUN curl -fsSL https://ftp.gnu.org/gnu/gnucobol/gnucobol-3.2.tar.xz -o gnucobol.tar.xz \
    && echo '3bb48af46ced4779facf41fdc2ee60e4ccb86eaa99d010b36685315df39c2ee2  gnucobol.tar.xz' | sha256sum -c - \
    && tar -xf gnucobol.tar.xz && cd gnucobol-3.2 \
    && ./configure --prefix=/usr/local --without-db --without-curses \
    && make -j4 && make install && ldconfig
WORKDIR /app
COPY engine/ engine/
RUN python engine/build.py

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgmp10 \
    && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home boreal
COPY --from=compiler /usr/local/lib/libcob* /usr/local/lib/
RUN ldconfig
WORKDIR /app
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
COPY --chown=boreal:boreal backend/ backend/
COPY --chown=boreal:boreal migrations/ migrations/
COPY --chown=boreal:boreal fixtures/ fixtures/
COPY --chown=boreal:boreal scripts/ scripts/
COPY --chown=boreal:boreal docs/ docs/
COPY --chown=boreal:boreal artifacts/ artifacts/
COPY --chown=boreal:boreal README.md DEMO.md CONTRACT.md /app/
COPY --from=compiler --chown=boreal:boreal /app/engine /app/engine
COPY --from=frontend --chown=boreal:boreal /ui/dist /app/frontend/dist
RUN mkdir -p /app/.local && chown boreal:boreal /app/.local
ENV PYTHONPATH=/app/backend:/app PYTHONUNBUFFERED=1 BOREAL_ENGINE_BUILDS=/app/.local/engine-builds
USER boreal
EXPOSE 8000
ENTRYPOINT ["python", "scripts/container_entrypoint.py"]
CMD ["python", "-m", "uvicorn", "boreal.api:app", "--host", "0.0.0.0", "--port", "8000"]
