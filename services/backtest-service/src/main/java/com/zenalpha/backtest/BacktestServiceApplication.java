package com.zenalpha.backtest;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

@SpringBootApplication(scanBasePackages = {"com.zenalpha.backtest", "com.zenalpha.common"})
@EnableDiscoveryClient
public class BacktestServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(BacktestServiceApplication.class, args);
    }
}
