package com.cobi.cobi_app.service;

import com.cobi.cobi_app.model.User;
import com.cobi.cobi_app.model.Otp;
import com.cobi.cobi_app.repository.UserRepository;
import com.cobi.cobi_app.repository.OtpRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.Random;

@Service
public class UserService {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private OtpRepository otpRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private EmailService emailService;

    public User createUser(User user) {
        user.setPassword(passwordEncoder.encode(user.getPassword()));
        user.setCreatedAt(LocalDateTime.now());
        user.setVerified(false);
        User savedUser = userRepository.save(user);

        // Send OTP after saving user
        generateOtp(savedUser);

        return savedUser;
    }

 public String generateOtp(User user) {
    String otpCode = String.format("%06d", new Random().nextInt(999999));
    Otp otp = new Otp();
    otp.setCode(otpCode);
    otp.setCreatedAt(LocalDateTime.now());
    otp.setExpiresAt(LocalDateTime.now().plusMinutes(10));
    otp.setUser(user);
    otpRepository.save(otp);

    try {
        emailService.sendOtpEmail(user.getEmail(), otpCode);
    } catch (Exception e) {
        System.err.println("Failed to send OTP email: " + e.getMessage());
        // Optionally log or notify admin
    }

    return "OTP sent to " + user.getEmail();
}


public String verifyOtp(String email, String code) {
    Optional<User> userOpt = userRepository.findByEmail(email);
    if (userOpt.isEmpty()) return "User not found";

    User user = userOpt.get();
    Otp otp = otpRepository.findTopByUserOrderByCreatedAtDesc(user);

    if (otp == null) return "No OTP found for user";
    if (!otp.getCode().equals(code)) return "Invalid OTP";
    if (otp.getExpiresAt().isBefore(LocalDateTime.now())) return "OTP expired";

    user.setVerified(true);
    userRepository.save(user);
    return "User verified successfully";
}

public Optional<User> findByEmail(String email) {
    return userRepository.findByEmail(email);
}


public boolean checkPassword(String rawPassword, String encodedPassword) {
    return passwordEncoder.matches(rawPassword, encodedPassword);
}

}
