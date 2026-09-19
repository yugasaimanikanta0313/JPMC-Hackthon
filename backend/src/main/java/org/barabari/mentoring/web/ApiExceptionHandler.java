package org.barabari.mentoring.web;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.*;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
@RestControllerAdvice
public class ApiExceptionHandler {
  @ExceptionHandler(MethodArgumentNotValidException.class) ResponseEntity<Map<String,Object>> validation(MethodArgumentNotValidException e){ return ResponseEntity.badRequest().body(Map.of("timestamp",Instant.now(),"code","VALIDATION_ERROR","message","Request validation failed")); }
}

