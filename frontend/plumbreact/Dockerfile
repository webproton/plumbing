# Stage 1: Build React
FROM node:18-bullseye as build
WORKDIR /app

# react-snap требует Chromium
RUN apt-get update && apt-get install -y \
  chromium \
  --no-install-recommends && rm -rf /var/lib/apt/lists/*

# puppeteer (react-snap) ищет браузер по этой переменной
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Перед копированием зависимостей, объявляем аргумент
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL

COPY package.json yarn.lock ./

#<- используем --frozen-lockfile
RUN yarn install --frozen-lockfile   
COPY . .

RUN yarn build
# RUN yarn postbuild

# Stage 2: Nginx only for serving build
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY ./nginx.conf /etc/nginx/conf.d/default.conf