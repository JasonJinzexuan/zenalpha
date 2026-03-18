# Build stage
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY common/pom.xml common/
COPY backtest-service/pom.xml backtest-service/
RUN mvn dependency:go-offline -pl backtest-service -am
COPY common/src common/src
COPY backtest-service/src backtest-service/src
RUN mvn package -pl backtest-service -am -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/backtest-service/target/*.jar app.jar
EXPOSE 8082
ENTRYPOINT ["java", "-jar", "app.jar"]
