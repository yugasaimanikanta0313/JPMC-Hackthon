package org.barabari.mentoring.repository;
import java.util.Optional;
import org.barabari.mentoring.domain.*;
import org.springframework.data.mongodb.repository.MongoRepository;
public interface UserRepository extends MongoRepository<User,String> { Optional<User> findByEmail(String email); boolean existsByRolesContaining(Role role); }

