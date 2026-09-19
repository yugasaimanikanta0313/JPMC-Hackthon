package org.barabari.mentoring.domain;
import java.time.Instant;
import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
@Document("projects") @Data @Builder @NoArgsConstructor @AllArgsConstructor
public class Project { @Id private String id; private String name; private String summary; private String status; private Instant createdAt; }

