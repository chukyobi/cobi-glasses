package com.cobi.cobi_app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class CobiAppApplication {

	public static void main(String[] args) {
		SpringApplication.run(CobiAppApplication.class, args);
	}

}
