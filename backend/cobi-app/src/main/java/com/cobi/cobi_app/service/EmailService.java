package com.cobi.cobi_app.service;

import com.sendgrid.*;
import com.sendgrid.helpers.mail.Mail;
import com.sendgrid.helpers.mail.objects.Content;
import com.sendgrid.helpers.mail.objects.Email;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;

import java.io.IOException;

@Service
public class EmailService {

    @Value("${sendgrid.api.key}")
    private String sendGridApiKey;

    @Value("${sendgrid.sender.email}")
    private String senderEmail;

    @Value("${email.provider:smtp}") // defaults to smtp if not set
    private String emailProvider;

    private final JavaMailSender mailSender;

    public EmailService(JavaMailSender mailSender) {
        this.mailSender = mailSender;
    }

    @Async
    public void sendOtpEmail(String to, String otpCode) {
        if ("sendgrid".equalsIgnoreCase(emailProvider)) {
            sendViaSendGrid(to, otpCode);
        } else {
            sendViaSmtp(to, otpCode);
        }
    }

    private void sendViaSendGrid(String to, String otpCode) {
        try {
            Email from = new Email(senderEmail);
            String subject = "Your Cobi Verification Code";
            Email toEmail = new Email(to);
            
            String htmlContent = "<div style='font-family: Arial, sans-serif; padding: 20px;'>" +
                    "<h2 style='color: #3b82f6;'>Welcome to Cobi!</h2>" +
                    "<p>Your verification code is:</p>" +
                    "<div style='background-color: #f3f4f6; padding: 15px; border-radius: 8px; text-align: center;'>" +
                    "<h1 style='color: #1f2937; letter-spacing: 8px; margin: 0;'>" + otpCode + "</h1>" +
                    "</div>" +
                    "<p style='color: #6b7280; margin-top: 20px;'>This code will expire in 10 minutes.</p>" +
                    "<p>If you didn't request this code, please ignore this email.</p>" +
                    "<p style='margin-top: 30px;'>Best regards,<br/>The Cobi Team</p>" +
                    "</div>";
            
            Content content = new Content("text/html", htmlContent);
            Mail mail = new Mail(from, subject, toEmail, content);

            SendGrid sg = new SendGrid(sendGridApiKey);
            Request request = new Request();
            request.setMethod(Method.POST);
            request.setEndpoint("mail/send");
            request.setBody(mail.build());
            Response response = sg.api(request);

            System.out.println("SendGrid email sent with status code: " + response.getStatusCode());
        } catch (IOException ex) {
            System.err.println("Error sending email via SendGrid: " + ex.getMessage());
            ex.printStackTrace();
        }
    }

    private void sendViaSmtp(String to, String otpCode) {
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");
            
            helper.setFrom(senderEmail);
            helper.setTo(to);
            helper.setSubject("Your Cobi Verification Code");
            
            String htmlContent = "<div style='font-family: Arial, sans-serif; padding: 20px;'>" +
                    "<h2 style='color: #3b82f6;'>Welcome to Cobi!</h2>" +
                    "<p>Your verification code is:</p>" +
                    "<div style='background-color: #f3f4f6; padding: 15px; border-radius: 8px; text-align: center;'>" +
                    "<h1 style='color: #1f2937; letter-spacing: 8px; margin: 0;'>" + otpCode + "</h1>" +
                    "</div>" +
                    "<p style='color: #6b7280; margin-top: 20px;'>This code will expire in 10 minutes.</p>" +
                    "<p>If you didn't request this code, please ignore this email.</p>" +
                    "<p style='margin-top: 30px;'>Best regards,<br/>The Cobi Team</p>" +
                    "</div>";
            
            helper.setText(htmlContent, true);
            
            mailSender.send(message);
            System.out.println("SMTP email sent successfully to: " + to);
        } catch (MessagingException ex) {
            System.err.println("Error sending email via SMTP: " + ex.getMessage());
            ex.printStackTrace();
        }
    }
}
