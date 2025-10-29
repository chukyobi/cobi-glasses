package com.cobi.cobi_app.controller;

import com.cobi.cobi_app.model.User;
import com.cobi.cobi_app.security.JwtUtil;
import com.cobi.cobi_app.service.UserService;
import com.cobi.cobi_app.dto.LoginRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @Autowired
    private UserService userService;

    @Autowired
    private JwtUtil jwtUtil;

    @PostMapping("/create")
    public ResponseEntity<?> createUser(@RequestBody User user) {
        try {
            User createdUser = userService.createUser(user);
            return ResponseEntity.ok(createdUser);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body("Error creating user: " + e.getMessage());
        }
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        Optional<User> userOpt = userService.findByEmail(request.getEmail());
        if (userOpt.isEmpty()) {
            return ResponseEntity.status(401).body("User not found");
        }

        User user = userOpt.get();

        if (!user.isVerified()) {
            return ResponseEntity.status(403).body("User not verified");
        }

        if (!userService.checkPassword(request.getPassword(), user.getPassword())) {
            return ResponseEntity.status(401).body("Invalid credentials");
        }

        String token = jwtUtil.generateToken(user.getEmail());

        // Build combined response
        Map<String, Object> response = new HashMap<>();
        response.put("token", token);

        // Exclude password for security
        user.setPassword(null);
        response.put("user", user);

        return ResponseEntity.ok(response);
    }

    @GetMapping("/me")
    public ResponseEntity<?> getCurrentUser(@RequestHeader(value = "Authorization", required = false) String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return ResponseEntity.status(401).body("Missing or invalid Authorization header");
        }

        String token = authHeader.substring(7);
        String email = jwtUtil.extractUsername(token);

        if (!jwtUtil.validateToken(token, email)) {
            return ResponseEntity.status(401).body("Invalid or expired token");
        }

        Optional<User> userOpt = userService.findByEmail(email);
        if (userOpt.isEmpty()) {
            return ResponseEntity.status(404).body("User not found");
        }

        User user = userOpt.get();
        user.setPassword(null); // remove password from response
        return ResponseEntity.ok(user);
    }
}
