# syntax=docker/dockerfile:1
# Angular 20 SSR app (fundi-pro). Targets:
#   dev     - ng serve with live reload (used by docker-compose.dev.yml)
#   runtime - production Node/Express SSR server (default)

FROM node:22-alpine AS deps
ENV NG_CLI_ANALYTICS=false
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM deps AS dev
COPY . .
EXPOSE 4200
CMD ["npx", "ng", "serve", "--host", "0.0.0.0", "--port", "4200"]

FROM deps AS build
# Public base URL of the Django API as seen from the user's browser, with a
# trailing slash. Empty = keep src/environments/environment.prod.ts as is.
ARG API_URL=
COPY . .
RUN if [ -n "$API_URL" ]; then \
      case "$API_URL" in */) ;; *) API_URL="$API_URL/";; esac; \
      printf "export const environment = {\n  production: true,\n  apiUrl: '%s'\n};\n" "$API_URL" \
        > src/environments/environment.prod.ts; \
    fi \
 && npx ng build --configuration production

FROM node:22-alpine AS runtime
ENV NODE_ENV=production \
    PORT=4000
WORKDIR /app
COPY --from=build --chown=node:node /app/dist/fundi-pro ./dist/fundi-pro
USER node
EXPOSE 4000
CMD ["node", "dist/fundi-pro/server/server.mjs"]
