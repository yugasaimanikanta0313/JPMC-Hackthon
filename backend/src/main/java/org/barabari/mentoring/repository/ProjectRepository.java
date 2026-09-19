package org.barabari.mentoring.repository;
import org.barabari.mentoring.domain.Project;
import org.springframework.data.mongodb.repository.MongoRepository;
public interface ProjectRepository extends MongoRepository<Project,String> {}

