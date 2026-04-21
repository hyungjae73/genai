FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Startup script: start dev server with --force to bypass stale Vite cache
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--force"]
