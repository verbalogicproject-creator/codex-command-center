FROM node:22-bookworm-slim AS build

WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web ./
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build

FROM nginx:1.27-alpine

ENV PORT=8080 \
    API_ORIGIN=http://127.0.0.1:8000 \
    NGINX_ENVSUBST_FILTER="^(PORT|API_ORIGIN)$"

COPY deploy/web/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /build/apps/web/out /usr/share/nginx/html

EXPOSE 8080
