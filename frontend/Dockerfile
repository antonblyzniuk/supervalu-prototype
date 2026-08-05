# syntax=docker/dockerfile:1

# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------
FROM node:24-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# --------------------------------------------------------------------------
# Development — Vite dev server with HMR
# --------------------------------------------------------------------------
FROM node:24-alpine AS dev

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# --------------------------------------------------------------------------
# Build — static production bundle
# --------------------------------------------------------------------------
FROM node:24-alpine AS build

WORKDIR /app

# Vite inlines env vars at build time, so the API base must be known here.
# Default "/api" keeps the app same-origin behind the nginx proxy below.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --------------------------------------------------------------------------
# Production — nginx serving the bundle and proxying the API
# --------------------------------------------------------------------------
FROM nginx:1.27-alpine AS prod

# Substituted into the config at start-up. Railway overrides PORT itself;
# BACKEND_ORIGIN must be set to the backend service's URL.
# NGINX_ENTRYPOINT_LOCAL_RESOLVERS makes the image's 15-local-resolvers script
# export NGINX_LOCAL_RESOLVERS from /etc/resolv.conf — it is opt-in, and the
# config below needs it for the runtime-resolved upstream.
ENV PORT=80 \
    BACKEND_ORIGIN=http://backend:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 \
    NGINX_ENVSUBST_FILTER='^(PORT|BACKEND_ORIGIN|NGINX_LOCAL_RESOLVERS)$'

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
