# Build stage
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY common/pom.xml common/
COPY eureka-server/pom.xml eureka-server/
RUN mvn dependency:go-offline -pl eureka-server -am
COPY common/src common/src
COPY eureka-server/src eureka-server/src
RUN mvn package -pl eureka-server -am -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/eureka-server/target/*.jar app.jar
EXPOSE 8761
ENTRYPOINT ["java", "-jar", "app.jar"]
