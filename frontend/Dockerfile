FROM node:20-slim

WORKDIR /app

ENV NODE_OPTIONS=--dns-result-order=ipv4first

COPY package*.json ./
COPY .npmrc ./
# Copy local node_modules instead of installing (network bypass)
COPY node_modules ./node_modules
# RUN npm config set registry http://registry.npmmirror.com
# RUN npm config set strict-ssl false
# RUN npm config set fetch-retry-maxtimeout 60000
# RUN npm install --no-audit --no-fund --verbose

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
