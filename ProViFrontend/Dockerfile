ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

FROM node:22-alpine
# Pinned: npm's own bundled deps (undici, brace-expansion, tar, ip-address)
# end up in the image and are scanned by Trivy. 12.2.1 ships patched versions.
RUN apk update && apk upgrade --no-cache && \
    npm install -g npm@12.2.1

WORKDIR /app
COPY ./provi-frontend/package*.json ./provi-frontend/
RUN npm install --prefix ./provi-frontend && \
    npm install --prefix ./provi-frontend sharp
COPY . .
WORKDIR /app/provi-frontend

EXPOSE 3000

# The app calls the backend at the relative path /api/..., which next.config.mjs
# rewrites to BACKEND_INTERNAL_URL at request time. Nothing about the deployment
# host is baked into the bundle.

RUN npm run build
CMD ["npm", "run", "start"]
