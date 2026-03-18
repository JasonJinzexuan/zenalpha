FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY . .
RUN mvn package -DskipTests -B -q && \
    find . -name "*.jar" -path "*/target/*" ! -name "original-*" -exec ls -la {} \;
