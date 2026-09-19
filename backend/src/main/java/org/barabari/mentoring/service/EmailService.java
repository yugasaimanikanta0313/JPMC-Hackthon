package org.barabari.mentoring.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.MailException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

@Service
public class EmailService {
  private final JavaMailSender mailSender;
  private final String from;
  private final String frontendUrl;

  public EmailService(JavaMailSender mailSender,
      @Value("${app.mail-from}") String from,
      @Value("${app.frontend-url}") String frontendUrl) {
    this.mailSender = mailSender;
    this.from = from;
    this.frontendUrl = frontendUrl;
  }

  public void sendInvitation(String recipient, String token, String role) {
    SimpleMailMessage message = new SimpleMailMessage();
    message.setFrom(from);
    message.setTo(recipient);
    message.setSubject("You are invited to Barabari");
    message.setText("""
      You have been invited to the Barabari Intelligent Project Mentoring Platform.

      Assigned role: %s

      Accept your invitation:
      %s/invite/%s

      This invitation is single-use and expires in 48 hours. If you were not expecting
      this invitation, you can safely ignore this message.
      """.formatted(role, frontendUrl, token));
    try {
      mailSender.send(message);
    } catch (MailException exception) {
      throw new IllegalStateException("Invitation was created, but email delivery failed. Check SMTP configuration.", exception);
    }
  }

  public void sendPasswordReset(String recipient, String token) {
    SimpleMailMessage message = new SimpleMailMessage();
    message.setFrom(from);
    message.setTo(recipient);
    message.setSubject("Reset your Barabari password");
    message.setText("Reset your password using this single-use link (valid for 30 minutes):\n\n"
      + frontendUrl + "/reset-password?token=" + token
      + "\n\nIf you did not request this, ignore this email.");
    mailSender.send(message);
  }
}
