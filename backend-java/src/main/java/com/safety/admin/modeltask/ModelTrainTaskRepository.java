package com.safety.admin.modeltask;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ModelTrainTaskRepository extends JpaRepository<ModelTrainTask, Long> {

    Optional<ModelTrainTask> findTopByOrderByIdDesc();
}
