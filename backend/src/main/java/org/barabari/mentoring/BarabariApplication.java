package org.barabari.mentoring;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import java.nio.file.*;

@SpringBootApplication
public class BarabariApplication {
  public static void main(String[] args) {
    loadLocalEnvironment();
    enableLocalFallbackWhenMongoIsInvalid();
    SpringApplication.run(BarabariApplication.class, args);
  }

  private static void enableLocalFallbackWhenMongoIsInvalid() {
    String uri = System.getProperty("MONGODB_URI", "");
    if (uri.startsWith("mongodb://") || uri.startsWith("mongodb+srv://")) return;
    System.setProperty("spring.autoconfigure.exclude",
      "org.springframework.boot.autoconfigure.mongo.MongoAutoConfiguration," +
      "org.springframework.boot.autoconfigure.data.mongo.MongoDataAutoConfiguration," +
      "org.springframework.boot.autoconfigure.data.mongo.MongoRepositoriesAutoConfiguration");
  }

  private static void loadLocalEnvironment() {
    Path file = Path.of("..", ".env").normalize();
    if (!Files.isRegularFile(file)) return;
    try {
      for (String line : Files.readAllLines(file)) {
        String value = line.trim();
        if (value.isEmpty() || value.startsWith("#") || !value.contains("=")) continue;
        int separator = value.indexOf('=');
        String key = value.substring(0, separator).trim();
        String secret = value.substring(separator + 1).trim();
        if (System.getenv(key) == null && System.getProperty(key) == null) System.setProperty(key, secret);
      }
    } catch (Exception exception) {
      throw new IllegalStateException("Unable to load local environment configuration", exception);
    }
  }
}
