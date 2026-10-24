# ------------------------------------------------------------------------------
# Stage 1: Build de la aplicación Vite + React
# ------------------------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Servidor estático Nginx para producción
# ------------------------------------------------------------------------------
FROM nginx:alpine

# Configurar fallback para rutas de React Router (SPA)
RUN printf 'server {\n\
    listen 80;\n\
    location / {\n\
        root /usr/share/nginx/html;\n\
        index index.html index.htm;\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
