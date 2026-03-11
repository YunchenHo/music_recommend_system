FROM node:22-alpine

WORKDIR /app

# 先安裝依賴套件 (利用 Docker 快取加速)
COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 5173

# 啟動前端開發伺服器
CMD ["npm", "run", "dev", "--", "--host"]