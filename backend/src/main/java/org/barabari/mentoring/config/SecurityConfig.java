package org.barabari.mentoring.config;

import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.http.HttpMethod;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.*;

@Configuration @EnableMethodSecurity
public class SecurityConfig {
  @Bean PasswordEncoder passwordEncoder(){ return new BCryptPasswordEncoder(12); }
  @Bean CorsConfigurationSource cors(@Value("${app.frontend-url}") String origin){
    var c=new CorsConfiguration(); c.setAllowedOriginPatterns(List.of("http://localhost:*","http://127.0.0.1:*")); c.setAllowedMethods(List.of("GET","POST","PUT","PATCH","DELETE","OPTIONS")); c.setAllowedHeaders(List.of("*")); c.setAllowCredentials(true);
    var source=new UrlBasedCorsConfigurationSource(); source.registerCorsConfiguration("/**",c); return source;
  }
  @Bean SecurityFilterChain security(HttpSecurity http) throws Exception {
    return http.csrf(c->c.disable()).cors(c->{}).authorizeHttpRequests(a->a
      .requestMatchers(HttpMethod.OPTIONS,"/**").permitAll()
      .requestMatchers("/actuator/health","/api/health","/api/auth/**","/error").permitAll()
      .anyRequest().permitAll()).build();
  }
}
