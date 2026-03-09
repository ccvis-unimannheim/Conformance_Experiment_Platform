ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

FROM node:18-alpine

WORKDIR /app
COPY ./provi-frontend/package*.json ./provi-frontend/
RUN npm install --prefix ./provi-frontend
COPY . .
WORKDIR /app/provi-frontend
EXPOSE 3000
RUN npm run build 
CMD npm run start 