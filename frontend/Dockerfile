# ==============================================================================
# AeroCast-Now AI: Hardened Multi-Stage Frontend Dockerfile (Phase 12)
# ==============================================================================

# Stage 1: Build Static Assets with Node.js
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency specifications and install with clean install
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source files
COPY . .

# Compile TypeScript and bundle with Vite
RUN npm run build


# Stage 2: Serve Static Bundle via Unprivileged Nginx
FROM nginxinc/nginx-unprivileged:alpine AS runtime

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy unprivileged Nginx server configuration
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080

# Healthcheck
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget -q -O - http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
