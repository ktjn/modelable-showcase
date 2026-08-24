# Modelable Showcase web image (IMPLEMENTATION_PLAN.md Task 11.1).
#
# Build context MUST be the repository root: `docker build -f apps/web/Dockerfile .`
# (docker-compose.yml sets this). Mirrors apps/api/Dockerfile's design:
# see its header comment for the generator-stage rationale (option 2 -
# `docker compose up --build` needs no manual `make generate` step).
#
#   1. generator - installs the pinned Modelable CLI and compiles model/
#      into generated/typescript, which vite.config.ts's "@generated" alias
#      (and this build) resolve directly - no copied/committed generated
#      files (SPEC.md Sec 4.1/9.1).
#   2. builder - npm ci + vite build against the generated types.
#   3. runtime - nginx serving the static build, proxying /api, /openapi.json,
#      and /docs to the api container the same way vite.config.ts's dev
#      server proxy does, so src/api/client.ts's same-origin relative paths
#      work unchanged in both dev and this container (apps/api has no CORS
#      middleware).

FROM ghcr.io/astral-sh/uv:bookworm-slim AS generator
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY .modelable-version ./
COPY model ./model
COPY scripts/install-modelable.sh scripts/modelable-env.sh ./scripts/
RUN bash scripts/install-modelable.sh
RUN bash -lc '. scripts/modelable-env.sh && modelable compile model --target typescript --out generated/typescript'

FROM node:24-slim AS builder
WORKDIR /workspace
COPY --from=generator /workspace/generated/typescript ./generated/typescript
COPY apps/web ./apps/web
WORKDIR /workspace/apps/web
RUN npm ci
RUN npm run build

FROM nginx:1-alpine AS runtime
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html
EXPOSE 80
