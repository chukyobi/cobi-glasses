package com.cobi.cobi_app.service;

import com.sendgrid.*;
import com.sendgrid.helpers.mail.Mail;
import com.sendgrid.helpers.mail.objects.Content;
import com.sendgrid.helpers.mail.objects.Email;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.io.IOException;

@Service
public class EmailService {

    @Value("${sendgrid.api.key}")
    private String sendGridApiKey;

    @Value("${sendgrid.sender.email}")
    private String senderEmail;

    @Async
    public void sendOtpEmail(String to, String otpCode) {
        Email from = new Email(senderEmail);
        String subject = "Your Oucla OTP Code";
        Email toEmail = new Email(to);
        Content content = new Content("text/plain",
                "Hello,\n\nYour OTP code is: " + otpCode +
                "\n\nThis code will expire in 10 minutes.\n\nRegards,\nOucla Team");

        Mail mail = new Mail(from, subject, toEmail, content);

        SendGrid sg = new SendGrid(sendGridApiKey);
        Request request = new Request();

        try {
            request.setMethod(Method.POST);
            request.setEndpoint("mail/send");
            request.setBody(mail.build());
            Response response = sg.api(request);

            System.out.println("Email sent with status code: " + response.getStatusCode());
        } catch (IOException ex) {
            System.err.println("Error sending email: " + ex.getMessage());
        }
    }
}
