# Build the Vue application. Node.js is needed in this stage only.
FROM node:22-bookworm-slim AS build
WORKDIR /app

# Keep dependency installation cached when only application code changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.js ./
COPY src ./src
COPY public ./public

# Vite embeds these public values into JavaScript at build time.
# Never pass passwords, JWT secrets, or private API keys through VITE_*.
ARG VITE_DEMO_MODE=false
ARG VITE_AUTH_API_URL=http://localhost:8080
ARG VITE_LOGIN_PATH=/api/auth/login
ARG VITE_SIGNUP_PATH=/api/auth/signup
ARG VITE_RAG_API_URL=http://localhost:8002
ARG VITE_INTERNAL_RAG_API_URL=http://localhost:8002
ARG VITE_RECOMMEND_API_URL=http://localhost:8002
ENV VITE_DEMO_MODE=${VITE_DEMO_MODE} \
    VITE_AUTH_API_URL=${VITE_AUTH_API_URL} \
    VITE_LOGIN_PATH=${VITE_LOGIN_PATH} \
    VITE_SIGNUP_PATH=${VITE_SIGNUP_PATH} \
    VITE_RAG_API_URL=${VITE_RAG_API_URL} \
    VITE_INTERNAL_RAG_API_URL=${VITE_INTERNAL_RAG_API_URL} \
    VITE_RECOMMEND_API_URL=${VITE_RECOMMEND_API_URL}
RUN npm run build

# Serve only the generated files; Node.js and source code stay in the build stage.
FROM nginx:stable-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1
