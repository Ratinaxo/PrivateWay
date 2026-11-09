# Node 26 como en el entorno local del proyecto. El lockfile pnpm es obligatorio.
FROM node:26-bookworm-slim AS base
WORKDIR /app
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    NEXT_TELEMETRY_DISABLED=1
RUN npm install --global corepack && corepack enable

FROM base AS dependencies
# pnpm-workspace.yaml contiene allowBuilds y forma parte de la instalación reproducible.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM dependencies AS development
COPY --chown=node:node . .
RUN chown -R node:node /app
USER node
EXPOSE 3000
CMD ["./node_modules/.bin/next", "dev", "-H", "0.0.0.0", "-p", "3000"]

FROM development AS build
ENV NODE_ENV=production
RUN pnpm build

FROM node:26-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
# Sin requerir output: standalone ni modificar next.config.ts.
COPY --from=build --chown=node:node /app /app
USER node
EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
