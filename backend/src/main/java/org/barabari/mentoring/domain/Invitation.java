package org.barabari.mentoring.domain;

import java.time.Instant;
import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

@Document("invitations") @Data @Builder @NoArgsConstructor @AllArgsConstructor
public class Invitation {
  public enum Status { PENDING, ACCEPTED, EXPIRED, REVOKED }
  @Id private String id;
  @Indexed private String email;
  private Role role;
  private String projectId;
  private String invitedBy;
  @Indexed(unique=true) private String tokenHash;
  @Indexed private Status status;
  @Indexed(expireAfter="0s") private Instant expiresAt;
  private Instant createdAt;
  private Instant acceptedAt;
}

