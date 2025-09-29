package com.cobi.cobi_app.service;

import org.springframework.stereotype.Service;

@Service
public class EmailService {
    public void sendOtpEmail(String to, String otpCode) {
        // Implement actual email sending logic here
        System.out.println("Sending OTP " + otpCode + " to " + to);
    }
}
