package com.cobi.cobi_app.controller;

import com.cobi.cobi_app.model.User;
import com.cobi.cobi_app.security.JwtUtil;
import com.cobi.cobi_app.service.UserService;
import com.cobi.cobi_app.dto.LoginRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Optional;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @Autowired
    private UserService userService;

    @Autowired
    private JwtUtil jwtUtil;

    @PostMapping("/create")
    public ResponseEntity<User> createUser(@RequestBody User user) {
        return ResponseEntity.ok(userService.createUser(user));
    }

    @PostMapping("/login")
    public ResponseEntity<String> login(@RequestBody LoginRequest request) {
        Optional<User> userOpt = userService.findByEmail(request.getEmail());
        if (userOpt.isEmpty()) return ResponseEntity.status(401).body("User not found");

        User user = userOpt.get();
        if (!user.isVerified()) return ResponseEntity.status(403).body("User not verified");

        if (!userService.checkPassword(request.getPassword(), user.getPassword())) {
            return ResponseEntity.status(401).body("Invalid credentials");
        }

        String token = jwtUtil.generateToken(user.getEmail());
        return ResponseEntity.ok(token);
    }
}
