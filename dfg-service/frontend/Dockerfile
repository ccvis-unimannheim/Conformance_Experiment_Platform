ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

FROM node:22-alpine
RUN apk update && apk upgrade --no-cache && \
    npm install -g npm@latest

WORKDIR /app
COPY ./package*.json ./
RUN npm install && npm install sharp
COPY . .

EXPOSE 3000

# The app calls the backend at the relative path /dfg/api/..., which
# next.config.mjs rewrites to BACKEND_INTERNAL_URL at request time. Nothing
# about the deployment host is baked into the bundle.

RUN npm run build
CMD ["npm", "run", "start"]
