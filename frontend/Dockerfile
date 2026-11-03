FROM nginxinc/nginx-unprivileged:1.28-alpine

# The official image renders /etc/nginx/templates/*.template with envsubst at
# startup, so the API gateway address is configurable (Docker Compose uses the
# default; Kubernetes sets it to the gateway Service name).
ENV API_GATEWAY_URL=http://api-gateway:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY index.html app.js styles.css /usr/share/nginx/html/
COPY images/ /usr/share/nginx/html/images/

EXPOSE 8080
