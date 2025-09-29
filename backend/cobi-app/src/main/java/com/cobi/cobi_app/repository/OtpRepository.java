package com.cobi.cobi_app.repository;

import com.cobi.cobi_app.model.Otp;
import com.cobi.cobi_app.model.User;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OtpRepository extends JpaRepository<Otp, Long> {
    Otp findTopByUserOrderByCreatedAtDesc(User user);
}
