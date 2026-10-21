package com.safety.admin;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class SafetyAdminApplication {

    public static void main(String[] args) {
        SpringApplication.run(SafetyAdminApplication.class, args);
    }
}
