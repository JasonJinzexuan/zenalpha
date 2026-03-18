# Build stage
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY common/pom.xml common/
COPY gateway/pom.xml gateway/
RUN mvn dependency:go-offline -pl gateway -am
COPY common/src common/src
COPY gateway/src gateway/src
RUN mvn package -pl gateway -am -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/gateway/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
