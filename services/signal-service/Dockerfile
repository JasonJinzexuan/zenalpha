# Build stage
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY common/pom.xml common/
COPY signal-service/pom.xml signal-service/
RUN mvn dependency:go-offline -pl signal-service -am
COPY common/src common/src
COPY signal-service/src signal-service/src
RUN mvn package -pl signal-service -am -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/signal-service/target/*.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
