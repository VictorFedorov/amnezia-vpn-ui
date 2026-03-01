# Используем Node.js для разработки
FROM node:22-alpine

# Рабочая директория
WORKDIR /app

# Копируем файлы зависимостей
COPY package.json package-lock.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем исходный код
COPY . .

# Открываем порт
EXPOSE 5173

# Запускаем в режиме разработки с возможностью доступа извне контейнера
CMD ["npm", "run", "dev", "--", "--host"]
