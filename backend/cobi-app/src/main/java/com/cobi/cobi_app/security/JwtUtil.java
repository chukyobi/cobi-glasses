package com.cobi.cobi_app.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Component;

import java.security.Key;
import java.util.Date;

@Component
public class JwtUtil {

    // You can also load this from application.properties for consistency.
    private final Key key = Keys.secretKeyFor(SignatureAlgorithm.HS256);
    private final long expirationMs = 86400000; // 1 day

    // ✅ 1. Generate JWT token for user
    public String generateToken(String email) {
        return Jwts.builder()
                .setSubject(email)
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis() + expirationMs))
                .signWith(key)
                .compact();
    }

    // ✅ 2. Extract email (username) from token
    public String extractUsername(String token) {
        try {
            Claims claims = Jwts.parserBuilder()
                    .setSigningKey(key)
                    .build()
                    .parseClaimsJws(token)
                    .getBody();
            return claims.getSubject();
        } catch (JwtException e) {
            return null; // Invalid token
        }
    }

    // ✅ 3. Check if token is expired
    private boolean isTokenExpired(String token) {
        try {
            Claims claims = Jwts.parserBuilder()
                    .setSigningKey(key)
                    .build()
                    .parseClaimsJws(token)
                    .getBody();
            return claims.getExpiration().before(new Date());
        } catch (JwtException e) {
            return true; // Treat any parsing error as expired/invalid
        }
    }

    // ✅ 4. Validate token by comparing email and expiration
    public boolean validateToken(String token, String email) {
        String username = extractUsername(token);
        return (username != null && username.equals(email) && !isTokenExpired(token));
    }
}
