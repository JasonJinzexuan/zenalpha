# Build stage - use full source copy to resolve parent pom modules
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY common/ common/
COPY user-service/ user-service/
COPY eureka-server/pom.xml eureka-server/pom.xml
COPY gateway/pom.xml gateway/pom.xml
COPY signal-service/pom.xml signal-service/pom.xml
COPY backtest-service/pom.xml backtest-service/pom.xml
COPY data-service/pom.xml data-service/pom.xml
COPY notification-service/pom.xml notification-service/pom.xml
RUN mkdir -p eureka-server/src gateway/src signal-service/src backtest-service/src data-service/src notification-service/src
RUN mvn package -pl user-service -am -DskipTests -B -q

# Runtime stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/user-service/target/*.jar app.jar
EXPOSE 8084
ENTRYPOINT ["java", "-jar", "app.jar"]
