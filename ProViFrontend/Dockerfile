ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

FROM node:22-alpine
RUN apk update && apk upgrade --no-cache

WORKDIR /app
COPY ./provi-frontend/package*.json ./provi-frontend/
RUN npm install --prefix ./provi-frontend && \
    npm install --prefix ./provi-frontend sharp
COPY . .
WORKDIR /app/provi-frontend

EXPOSE 3000

ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build
CMD ["npm", "run", "start"]
