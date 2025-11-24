# Frontend Dockerfile for Ration Agent
# Multi-stage build for optimized Next.js production image

# Stage 1: Dependencies and build
FROM docker.1ms.run/node:20-alpine AS builder

# Metadata
LABEL maintainer="Kouprey POC Team"
LABEL version="1.0.0"
LABEL description="Next.js Frontend for Dairy Nutrition Formulation System"

# Install dependencies for building
RUN apk add --no-cache libc6-compat

# Set working directory
WORKDIR /app

# Set environment variables before package install for better caching
ENV NEXT_TELEMETRY_DISABLED=1

# Copy package files
COPY package*.json ./

# Install dependencies (include dev for building TypeScript/Next)
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev

# Copy source code
COPY . .

# Set build-time variables
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL

# Build the application
RUN npm run build

# Stage 2: Production runtime
FROM docker.1ms.run/node:20-alpine AS runtime

# Install dumb-init for proper signal handling and wget for healthcheck
RUN apk add --no-cache dumb-init wget

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Set working directory
WORKDIR /app

# Copy built application from builder stage
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Copy public folder
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Set environment variables
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider --prefer-family=IPv4 http://127.0.0.1:3000/api/health || exit 1

# Start the application with dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]
