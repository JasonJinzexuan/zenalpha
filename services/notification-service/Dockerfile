# Build stage
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY common/pom.xml common/
COPY notification-service/pom.xml notification-service/
RUN mvn dependency:go-offline -pl notification-service -am
COPY common/src common/src
COPY notification-service/src notification-service/src
RUN mvn package -pl notification-service -am -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/notification-service/target/*.jar app.jar
EXPOSE 8085
ENTRYPOINT ["java", "-jar", "app.jar"]
