FROM node:20-alpine

WORKDIR /srv/app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

ENV VITE_PROXY_TARGET=http://docgen-backend:8000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
