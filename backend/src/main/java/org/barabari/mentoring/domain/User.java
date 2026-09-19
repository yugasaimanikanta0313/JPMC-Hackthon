package org.barabari.mentoring.domain;

import java.time.Instant;
import java.util.HashSet;
import java.util.Set;
import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

@Document("users") @Data @Builder @NoArgsConstructor @AllArgsConstructor
public class User {
  @Id private String id;
  private String name;
  @Indexed(unique=true) private String email;
  private String passwordHash;
  @Builder.Default private Set<Role> roles = new HashSet<>();
  private String googleId;
  private String githubId;
  @Builder.Default private boolean active = true;
  @Builder.Default private Instant createdAt = Instant.now();
}

