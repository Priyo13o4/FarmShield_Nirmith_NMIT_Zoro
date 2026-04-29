# Build stage
FROM node:20-slim AS build
WORKDIR /app

# Install dependencies first for better caching
COPY package*.json ./
RUN npm install

# Copy source and build
COPY . .
# Set API URL to empty for relative paths (proxied by Nginx)
ENV VITE_API_URL=""
RUN npm run build

# Production stage
FROM nginx:alpine
# Copy build artifacts from build stage
COPY --from=build /app/dist /usr/share/nginx/html
# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
